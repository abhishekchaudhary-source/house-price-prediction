document.addEventListener('DOMContentLoaded', () => {
    let importanceChart = null;
    let debounceTimer = null;

    // Elements
    const form = document.getElementById('prediction-form');
    const presetsContainer = document.getElementById('preset-chips');
    const priceDisplay = document.getElementById('predicted-price-value');
    const priceRangeDisplay = document.getElementById('price-range');
    const pricePerSqftDisplay = document.getElementById('price-per-sqft');
    const mortgageDisplay = document.getElementById('mortgage-est');
    const bestModelBadge = document.getElementById('best-model-badge');
    const accuracyBadge = document.getElementById('accuracy-badge');
    const benchmarkTableBody = document.getElementById('benchmark-table-body');
    const btnReset = document.getElementById('btn-reset');

    // Initial Load
    init();

    async function init() {
        setupSliderListeners();
        await loadPresets();
        await loadMetadata();
        triggerPrediction();
    }

    // Connect Sliders to Badges
    function setupSliderListeners() {
        const sliders = [
            { id: 'sqft', badgeId: 'val-sqft', format: (val) => `${Number(val).toLocaleString()} sq ft` },
            { id: 'bedrooms', badgeId: 'val-bedrooms', format: (val) => `${val} Beds` },
            { id: 'bathrooms', badgeId: 'val-bathrooms', format: (val) => `${val} Baths` },
            { id: 'year_built', badgeId: 'val-year_built', format: (val) => `${val}` },
            { id: 'school_rating', badgeId: 'val-school_rating', format: (val) => `${val} / 10` },
            { id: 'distance_to_city_center_km', badgeId: 'val-distance', format: (val) => `${val} km` },
            { id: 'garage_cars', badgeId: 'val-garage', format: (val) => `${val} Cars` },
            { id: 'lot_size_sqft', badgeId: 'val-lot', format: (val) => `${Number(val).toLocaleString()} sq ft` }
        ];

        sliders.forEach(({ id, badgeId, format }) => {
            const input = document.getElementById(id);
            const badge = document.getElementById(badgeId);
            if (input && badge) {
                input.addEventListener('input', (e) => {
                    badge.innerText = format(e.target.value);
                    debouncePrediction();
                });
            }
        });

        // Location & Renovation listeners
        document.getElementById('location_tier').addEventListener('change', debouncePrediction);
        document.getElementById('renovated').addEventListener('change', debouncePrediction);

        btnReset.addEventListener('click', () => {
            form.reset();
            // Trigger input events to update badges
            sliders.forEach(({ id, badgeId, format }) => {
                const input = document.getElementById(id);
                const badge = document.getElementById(badgeId);
                if (input && badge) {
                    badge.innerText = format(input.value);
                }
            });
            triggerPrediction();
        });
    }

    function debouncePrediction() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            triggerPrediction();
        }, 150);
    }

    // Extract Form Payload
    function getFormData() {
        return {
            sqft: parseInt(document.getElementById('sqft').value, 10),
            bedrooms: parseInt(document.getElementById('bedrooms').value, 10),
            bathrooms: parseFloat(document.getElementById('bathrooms').value),
            location_tier: document.getElementById('location_tier').value,
            year_built: parseInt(document.getElementById('year_built').value, 10),
            school_rating: parseFloat(document.getElementById('school_rating').value),
            distance_to_city_center_km: parseFloat(document.getElementById('distance_to_city_center_km').value),
            garage_cars: parseInt(document.getElementById('garage_cars').value, 10),
            lot_size_sqft: parseInt(document.getElementById('lot_size_sqft').value, 10),
            renovated: document.getElementById('renovated').checked ? 1 : 0
        };
    }

    // Send API Request
    async function triggerPrediction() {
        try {
            const payload = getFormData();
            const response = await fetch('/api/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error('Prediction API error');
            const data = await response.json();

            updateUIWithPrediction(data);
        } catch (err) {
            console.error('Prediction failed:', err);
        }
    }

    // Update UI Elements with Prediction Results
    function updateUIWithPrediction(data) {
        // Animate price counter
        animateValue(priceDisplay, data.predicted_price);

        // Range
        priceRangeDisplay.innerText = `₹${data.confidence_range.min.toLocaleString('en-IN')} - ₹${data.confidence_range.max.toLocaleString('en-IN')}`;
        
        // Price per sqft
        pricePerSqftDisplay.innerText = `₹${data.price_per_sqft.toLocaleString('en-IN')} / sqft`;

        // Monthly mortgage / EMI
        mortgageDisplay.innerText = `₹${data.estimated_monthly_mortgage.toLocaleString('en-IN')} / mo`;
    }

    function animateValue(element, endVal) {
        const startVal = parseInt(element.innerText.replace(/,/g, ''), 10) || 0;
        const duration = 300;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const currentVal = Math.floor(startVal + (endVal - startVal) * progress);
            element.innerText = currentVal.toLocaleString('en-IN');

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                element.innerText = endVal.toLocaleString('en-IN');
            }
        }
        requestAnimationFrame(update);
    }

    // Load Presets
    async function loadPresets() {
        try {
            const res = await fetch('/api/presets');
            const presets = await res.json();

            presetsContainer.innerHTML = '';
            presets.forEach((p) => {
                const chip = document.createElement('button');
                chip.type = 'button';
                chip.className = 'chip';
                chip.innerText = p.name;
                chip.addEventListener('click', () => {
                    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
                    chip.classList.add('active');
                    applyPreset(p.data);
                });
                presetsContainer.appendChild(chip);
            });
        } catch (err) {
            console.error('Failed to load presets', err);
        }
    }

    function applyPreset(data) {
        document.getElementById('sqft').value = data.sqft;
        document.getElementById('bedrooms').value = data.bedrooms;
        document.getElementById('bathrooms').value = data.bathrooms;
        document.getElementById('location_tier').value = data.location_tier;
        document.getElementById('year_built').value = data.year_built;
        document.getElementById('school_rating').value = data.school_rating;
        document.getElementById('distance_to_city_center_km').value = data.distance_to_city_center_km;
        document.getElementById('garage_cars').value = data.garage_cars;
        document.getElementById('lot_size_sqft').value = data.lot_size_sqft;
        document.getElementById('renovated').checked = data.renovated === 1;

        // Dispatch input events
        const event = new Event('input');
        document.getElementById('sqft').dispatchEvent(event);
        document.getElementById('bedrooms').dispatchEvent(event);
        document.getElementById('bathrooms').dispatchEvent(event);
        document.getElementById('year_built').dispatchEvent(event);
        document.getElementById('school_rating').dispatchEvent(event);
        document.getElementById('distance_to_city_center_km').dispatchEvent(event);
        document.getElementById('garage_cars').dispatchEvent(event);
        document.getElementById('lot_size_sqft').dispatchEvent(event);

        triggerPrediction();
    }

    // Load Model Metadata & Benchmark Table
    async function loadMetadata() {
        try {
            const res = await fetch('/api/metadata');
            const meta = await res.json();

            const bestModel = meta.best_model;
            const bestMetrics = meta.metrics[bestModel];

            bestModelBadge.innerHTML = `<i class="fa-solid fa-microchip"></i> Model: <strong>${bestModel}</strong>`;
            accuracyBadge.innerHTML = `<i class="fa-solid fa-bullseye"></i> Accuracy R²: <strong>${(bestMetrics.r2_score * 100).toFixed(1)}%</strong>`;

            renderBenchmarkTable(meta.metrics, bestModel);
            renderChart(meta.feature_importances);
        } catch (err) {
            console.error('Failed to load metadata', err);
        }
    }

    function renderBenchmarkTable(metricsMap, bestModel) {
        benchmarkTableBody.innerHTML = '';
        for (const [modelName, m] of Object.entries(metricsMap)) {
            const isBest = modelName === bestModel;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${modelName}</strong></td>
                <td><span class="highlight-green">${(m.r2_score * 100).toFixed(2)}%</span></td>
                <td>₹${m.mae.toLocaleString('en-IN')}</td>
                <td>₹${m.rmse.toLocaleString('en-IN')}</td>
                <td>${(m.cv_r2_mean * 100).toFixed(2)}% ± ${(m.cv_r2_std * 100).toFixed(2)}%</td>
                <td>${isBest ? '<span class="status-best">🏆 Selected</span>' : '<span class="status-regular">Evaluated</span>'}</td>
            `;
            benchmarkTableBody.appendChild(tr);
        }
    }

    // Feature Importance Bar Chart
    function renderChart(importances) {
        const ctx = document.getElementById('importanceChart').getContext('2d');

        // Take top 7 importances
        const entries = Object.entries(importances).slice(0, 7);
        const labels = entries.map(([key]) => key.replace('cat__location_tier_', 'Loc: ').replace('num__', ''));
        const values = entries.map(([, val]) => (val * 100).toFixed(1));

        if (importanceChart) {
            importanceChart.destroy();
        }

        importanceChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Feature Importance (%)',
                    data: values,
                    backgroundColor: [
                        'rgba(16, 185, 129, 0.85)',
                        'rgba(6, 182, 212, 0.85)',
                        'rgba(139, 92, 246, 0.85)',
                        'rgba(245, 158, 11, 0.85)',
                        'rgba(59, 130, 246, 0.85)',
                        'rgba(236, 72, 153, 0.85)',
                        'rgba(107, 114, 128, 0.85)'
                    ],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        ticks: { color: '#9CA3AF', font: { size: 11 } },
                        grid: { display: false }
                    },
                    y: {
                        ticks: { color: '#9CA3AF', font: { size: 11 } },
                        grid: { color: 'rgba(255, 255, 255, 0.05)' }
                    }
                }
            }
        });
    }
});
