document.addEventListener('DOMContentLoaded', () => {
    let importanceChart = null;
    let debounceTimer = null;
    let bengaluruMap = null;
    let pinMarker = null;
    let localitiesList = [];

    // Central Business District Coordinates (Vidhana Soudha / MG Road, Bangalore)
    const CBD_COORDS = [12.9716, 77.5946];

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
        await initGeospatialMap();
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
        const locTierEl = document.getElementById('location_tier');
        if (locTierEl) locTierEl.addEventListener('change', debouncePrediction);

        const renoEl = document.getElementById('renovated');
        if (renoEl) renoEl.addEventListener('change', debouncePrediction);

        btnReset.addEventListener('click', () => {
            form.reset();
            sliders.forEach(({ id, badgeId, format }) => {
                const input = document.getElementById(id);
                const badge = document.getElementById(badgeId);
                if (input && badge) {
                    badge.innerText = format(input.value);
                }
            });
            // Reset map to Whitefield default
            if (bengaluruMap && pinMarker) {
                bengaluruMap.flyTo([12.9698, 77.7499], 12);
                pinMarker.setLatLng([12.9698, 77.7499]);
                updateLocationFromCoords(12.9698, 77.7499, 'Whitefield');
            }
            triggerPrediction();
        });
    }

    function debouncePrediction() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            triggerPrediction();
        }, 120);
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

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            updateUI(data);
        } catch (err) {
            console.error('Prediction API Error:', err);
        }
    }

    // Update UI with Prediction Values
    function updateUI(data) {
        animateValue(priceDisplay, data.predicted_price);

        // Price in Lakhs / Crores formatted badge
        const priceInLakhs = (data.predicted_price / 100000).toFixed(2);
        const priceLabel = data.predicted_price >= 10000000 
            ? `(₹${(data.predicted_price / 10000000).toFixed(2)} Cr)`
            : `(₹${priceInLakhs} Lakhs)`;

        priceRangeDisplay.innerText = `₹${formatINR(data.confidence_range.min)} - ₹${formatINR(data.confidence_range.max)}`;
        pricePerSqftDisplay.innerText = `₹${Number(data.price_per_sqft).toLocaleString('en-IN')}`;
        mortgageDisplay.innerText = `₹${Number(data.estimated_monthly_mortgage).toLocaleString('en-IN')}/mo`;

        // Update Nav Badges
        if (data.model_info) {
            bestModelBadge.innerHTML = `<i class="fa-solid fa-microchip"></i> Model: ${data.model_info.model_name}`;
            accuracyBadge.innerHTML = `<i class="fa-solid fa-bullseye"></i> Accuracy R²: ${(data.model_info.r2_score * 100).toFixed(1)}%`;
        }
    }

    // Smooth Number Animation
    function animateValue(element, target) {
        const duration = 250;
        const start = parseInt(element.innerText.replace(/,/g, ''), 10) || target * 0.8;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const current = Math.floor(start + (target - start) * progress);
            element.innerText = formatINR(current);

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }
        requestAnimationFrame(update);
    }

    function formatINR(val) {
        return Number(val).toLocaleString('en-IN');
    }

    // Load Presets
    async function loadPresets() {
        try {
            const res = await fetch('/api/presets');
            const presets = await res.json();
            presetsContainer.innerHTML = '';

            presets.forEach((p, index) => {
                const chip = document.createElement('div');
                chip.className = `preset-chip ${index === 1 ? 'active' : ''}`;
                chip.innerText = p.name;
                chip.addEventListener('click', () => {
                    document.querySelectorAll('.preset-chip').forEach(c => c.classList.remove('active'));
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
        ['sqft', 'bedrooms', 'bathrooms', 'year_built', 'school_rating', 'distance_to_city_center_km', 'garage_cars', 'lot_size_sqft'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.dispatchEvent(event);
        });

        // Sync Map to Preset Locality if defined
        if (data.locality && localitiesList.length > 0 && bengaluruMap && pinMarker) {
            const loc = localitiesList.find(l => l.name.toLowerCase().includes(data.locality.toLowerCase()));
            if (loc) {
                bengaluruMap.flyTo([loc.lat, loc.lng], 13, { duration: 1.0 });
                pinMarker.setLatLng([loc.lat, loc.lng]);
                updateLocationFromCoords(loc.lat, loc.lng, loc.name);
            }
        }

        triggerPrediction();
    }

    // Load Model Metadata & Benchmark Table
    async function loadMetadata() {
        try {
            const res = await fetch('/api/metadata');
            const meta = await res.json();

            // Populate Table
            benchmarkTableBody.innerHTML = '';
            for (const [modelName, m] of Object.entries(meta.metrics)) {
                const isBest = modelName === meta.best_model;
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><strong>${modelName}</strong></td>
                    <td>${m.r2_score.toFixed(4)}</td>
                    <td>₹${formatINR(m.mae)}</td>
                    <td>₹${formatINR(m.rmse)}</td>
                    <td>${m.cv_r2_mean.toFixed(4)}</td>
                    <td><span class="${isBest ? 'status-best' : 'status-regular'}">${isBest ? '🏆 BEST MODEL' : 'Evaluated'}</span></td>
                `;
                benchmarkTableBody.appendChild(row);
            }

            renderChart(meta.feature_importances);
        } catch (err) {
            console.error('Failed to load metadata', err);
        }
    }

    // Feature Importance Bar Chart
    function renderChart(importances) {
        const chartCanvas = document.getElementById('importanceChart');
        if (!chartCanvas) return;
        const ctx = chartCanvas.getContext('2d');

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

    // =========================================================================
    // 🗺️ GEOSPATIAL MAP & ADDRESS INTEGRATION (LEAFLET.JS)
    // =========================================================================

    // Haversine Distance Formula in Kilometers
    function calculateDistanceKm(lat1, lon1, lat2, lon2) {
        const R = 6371; // Earth's radius in km
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return Math.round(R * c * 10) / 10;
    }

    async function initGeospatialMap() {
        const mapContainer = document.getElementById('bengaluru-map');
        if (!mapContainer || typeof L === 'undefined') return;

        // 1. Fetch Bangalore Localities from API
        try {
            const res = await fetch('/api/localities');
            localitiesList = await res.json();
            populateLocalityDropdown(localitiesList);
        } catch (err) {
            console.warn('Could not load localities from /api/localities', err);
        }

        // 2. Initialize Leaflet Map centered on Whitefield / Bangalore
        const defaultLat = 12.9698;
        const defaultLng = 77.7499;

        bengaluruMap = L.map('bengaluru-map', {
            zoomControl: true,
            scrollWheelZoom: true
        }).setView([defaultLat, defaultLng], 12);

        // Dark/Voyager CartoDB Tile Layer
        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
            maxZoom: 19
        }).addTo(bengaluruMap);

        // Custom Pulsating Pin Marker
        const pinIcon = L.divIcon({
            className: 'custom-pin-wrapper',
            html: '<div class="marker-pulse"></div><div class="custom-pin-marker"></div>',
            iconSize: [28, 28],
            iconAnchor: [14, 28]
        });

        pinMarker = L.marker([defaultLat, defaultLng], {
            draggable: true,
            icon: pinIcon
        }).addTo(bengaluruMap);

        // Reference CBD Marker (MG Road / Vidhana Soudha)
        const cbdIcon = L.divIcon({
            className: 'cbd-icon',
            html: '<div style="background:#8B5CF6;color:#fff;font-size:10px;font-weight:700;padding:3px 8px;border-radius:12px;border:1px solid #fff;white-space:nowrap;box-shadow:0 2px 10px rgba(0,0,0,0.5);"><i class="fa-solid fa-landmark"></i> CBD (MG Road)</div>',
            iconAnchor: [45, 10]
        });
        L.marker(CBD_COORDS, { icon: cbdIcon, interactive: false }).addTo(bengaluruMap);

        // Connect CBD reference circle
        L.circle(CBD_COORDS, {
            radius: 5000,
            color: '#8B5CF6',
            fillColor: '#8B5CF6',
            fillOpacity: 0.05,
            weight: 1,
            dashArray: '4, 4'
        }).addTo(bengaluruMap);

        // Initial Location Calculation
        updateLocationFromCoords(defaultLat, defaultLng, 'Whitefield');

        // Click on map moves marker
        bengaluruMap.on('click', (e) => {
            pinMarker.setLatLng(e.latlng);
            updateLocationFromCoords(e.latlng.lat, e.latlng.lng);
        });

        // Drag marker moves location
        pinMarker.on('dragend', (e) => {
            const pos = e.target.getLatLng();
            updateLocationFromCoords(pos.lat, pos.lng);
        });

        // Setup Address Search, PDF Download, and Lead Capture Modal
        setupAddressSearch();
        setupPdfDownload();
        setupLeadModal();
    }

    function populateLocalityDropdown(localities) {
        const select = document.getElementById('locality_select');
        if (!select) return;
        select.innerHTML = '<option value="">-- Choose Locality --</option>';

        localities.forEach(loc => {
            const opt = document.createElement('option');
            opt.value = loc.name;
            opt.innerText = `${loc.name} (${loc.tier})`;
            if (loc.name === 'Whitefield') opt.selected = true;
            select.appendChild(opt);
        });
    }

    function updateLocationFromCoords(lat, lng, forcedLocality = null) {
        const dist = calculateDistanceKm(CBD_COORDS[0], CBD_COORDS[1], lat, lng);

        // Find closest locality name if not specified
        let detectedLocality = forcedLocality;
        let matchedTier = null;

        if (detectedLocality && localitiesList.length > 0) {
            const exact = localitiesList.find(l => l.name.toLowerCase() === detectedLocality.toLowerCase());
            if (exact) matchedTier = exact.tier;
        }

        if (!detectedLocality && localitiesList.length > 0) {
            let closestDist = Infinity;
            let closestName = 'Bengaluru Urban';
            localitiesList.forEach(loc => {
                const d = calculateDistanceKm(lat, lng, loc.lat, loc.lng);
                if (d < closestDist) {
                    closestDist = d;
                    closestName = loc.name;
                    matchedTier = loc.tier;
                }
            });
            detectedLocality = closestDist <= 4.0 ? closestName : `${closestName} Outskirts`;
        }

        if (!detectedLocality) detectedLocality = 'Bengaluru Urban';

        // Infer tier from proximity if not matched
        if (!matchedTier) {
            if (dist <= 5.5) matchedTier = 'Luxury';
            else if (dist <= 11.5) matchedTier = 'Prime';
            else if (dist <= 17.5) matchedTier = 'Urban';
            else if (dist <= 24.0) matchedTier = 'Suburban';
            else matchedTier = 'Budget';
        }

        // 1. Update Map Overlay
        const overlayDist = document.getElementById('overlay-distance');
        const overlayCoords = document.getElementById('overlay-coords');
        const overlayTier = document.getElementById('overlay-tier');

        if (overlayDist) overlayDist.innerText = `${dist.toFixed(1)} km`;
        if (overlayCoords) overlayCoords.innerText = `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E`;
        if (overlayTier) overlayTier.innerText = `${matchedTier} (${detectedLocality})`;

        // 2. Update Map Header Badges
        const locBadge = document.getElementById('map-locality-badge');
        const tierBadge = document.getElementById('map-tier-badge');
        if (locBadge) locBadge.innerHTML = `<i class="fa-solid fa-location-crosshairs"></i> Locality: ${detectedLocality}`;
        if (tierBadge) tierBadge.innerHTML = `<i class="fa-solid fa-layer-group"></i> Tier: ${matchedTier}`;

        // 3. Update Form Inputs (Sync Distance Slider & Locality Tier)
        const distInput = document.getElementById('distance_to_city_center_km');
        const distBadge = document.getElementById('val-distance');
        if (distInput) {
            const clampedDist = Math.min(35, Math.max(0.5, dist)).toFixed(1);
            distInput.value = clampedDist;
            if (distBadge) distBadge.innerText = `${clampedDist} km`;
        }

        const tierSelect = document.getElementById('location_tier');
        if (tierSelect && tierSelect.value !== matchedTier) {
            tierSelect.value = matchedTier;
        }

        debouncePrediction();
    }

    function setupAddressSearch() {
        const searchInput = document.getElementById('address-search-input');
        const searchBtn = document.getElementById('btn-search-address');
        const locSelect = document.getElementById('locality_select');

        // Locality Dropdown selection
        if (locSelect) {
            locSelect.addEventListener('change', (e) => {
                const selectedName = e.target.value;
                const loc = localitiesList.find(l => l.name === selectedName);
                if (loc && bengaluruMap && pinMarker) {
                    bengaluruMap.flyTo([loc.lat, loc.lng], 13, { duration: 1.0 });
                    pinMarker.setLatLng([loc.lat, loc.lng]);
                    updateLocationFromCoords(loc.lat, loc.lng, loc.name);
                }
            });
        }

        // Live OpenStreetMap Geocoding
        async function doSearch() {
            const query = searchInput.value.trim();
            if (!query) return;

            searchBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Searching...';
            try {
                const endpoint = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query + ', Bengaluru, Karnataka')}&limit=1`;
                const res = await fetch(endpoint, {
                    headers: { 'Accept-Language': 'en' }
                });
                const results = await res.json();

                if (results && results.length > 0) {
                    const lat = parseFloat(results[0].lat);
                    const lon = parseFloat(results[0].lon);

                    bengaluruMap.flyTo([lat, lon], 14, { duration: 1.2 });
                    pinMarker.setLatLng([lat, lon]);
                    updateLocationFromCoords(lat, lon, query);
                } else {
                    alert(`Could not find "${query}" in Bengaluru. Try a prominent society, metro station, or landmark.`);
                }
            } catch (err) {
                console.error('Geocoding search failed:', err);
                alert('Geocoding request failed. Please check internet connection.');
            } finally {
                searchBtn.innerHTML = '<i class="fa-solid fa-compass"></i> Search';
            }
        }

        if (searchBtn) searchBtn.addEventListener('click', doSearch);
        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    doSearch();
                }
            });
        }
    }

    function setupPdfDownload() {
        const btnDownload = document.getElementById('btn-download-report');
        if (btnDownload) {
            btnDownload.addEventListener('click', () => {
                window.print();
            });
        }
    }

    // Connect with Expert Lead Modal Handler
    function setupLeadModal() {
        const modal = document.getElementById('lead-modal');
        const btnOpen = document.getElementById('btn-open-lead-modal');
        const btnClose = document.getElementById('btn-close-lead-modal');
        const leadForm = document.getElementById('lead-form');
        const summaryText = document.getElementById('lead-summary-text');
        const leadMsg = document.getElementById('lead-form-msg');

        if (btnOpen && modal) {
            btnOpen.addEventListener('click', () => {
                const sqft = document.getElementById('sqft').value;
                const price = document.getElementById('predicted-price-value').innerText;
                const locSelect = document.getElementById('locality_select');
                const locality = (locSelect && locSelect.value) ? locSelect.value : 'Bengaluru';
                
                if (summaryText) {
                    summaryText.innerText = `${locality} | ${Number(sqft).toLocaleString()} sq ft | ₹${price}`;
                }
                modal.style.display = 'flex';
                if (leadMsg) leadMsg.innerHTML = '';
            });
        }

        if (btnClose && modal) {
            btnClose.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        }

        // Close on clicking backdrop
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.style.display = 'none';
            });
        }

        // Handle Form Submission
        if (leadForm) {
            leadForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const submitBtn = document.getElementById('btn-submit-lead');
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Submitting...';

                const name = document.getElementById('lead_name').value.trim();
                const phone = document.getElementById('lead_phone').value.trim();
                const email = document.getElementById('lead_email').value.trim();
                const locSelect = document.getElementById('locality_select');
                const locality = (locSelect && locSelect.value) ? locSelect.value : 'Bengaluru';
                const sqft = parseInt(document.getElementById('sqft').value, 10);
                const rawPrice = document.getElementById('predicted-price-value').innerText.replace(/,/g, '');
                const estPrice = parseFloat(rawPrice) || null;

                try {
                    const response = await fetch('/api/lead', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name: name,
                            phone: phone,
                            email: email,
                            locality: locality,
                            property_sqft: sqft,
                            estimated_price: estPrice
                        })
                    });

                    const data = await response.json();
                    if (response.ok) {
                        leadMsg.className = 'lead-msg success';
                        leadMsg.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + data.message;
                        leadForm.reset();
                        setTimeout(() => {
                            modal.style.display = 'none';
                            submitBtn.disabled = false;
                            submitBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Submit Inquiry';
                        }, 2200);
                    } else {
                        leadMsg.className = 'lead-msg error';
                        const errMsg = (data.validation_errors && data.validation_errors.length > 0)
                            ? data.validation_errors.join('<br>')
                            : data.message;
                        leadMsg.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + errMsg;
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Submit Inquiry';
                    }
                } catch (err) {
                    leadMsg.className = 'lead-msg error';
                    leadMsg.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error. Please try again.';
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Submit Inquiry';
                }
            });
        }
    }
});
