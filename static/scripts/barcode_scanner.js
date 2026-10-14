(() => {
    const scanner = document.querySelector('.photo-scanner');
    const canvas = document.getElementById('barcodescancanvas');
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    const start = document.getElementById('camera-start');
    const stop = document.getElementById('camera-stop');
    const choose = document.getElementById('image-choose');
    const input = document.getElementById('barcode-image');
    const picker = document.getElementById('camera-picker');
    const selector = document.getElementById('cameraSelector');
    const status = document.getElementById('scanner-status');
    const guide = document.getElementById('camera-guide');
    const success = document.getElementById('scanner-success');
    let guideTimer;
    const video = document.getElementById('camera-video');
    video.muted = true;
    video.playsInline = true;
    let reader;
    let stream;
    let generation = 0;
    let frame;
    let lastScan = 0;
    let detected = false;

    function switchGuide() {
        const next = { cassette: 'film', film: 'none', none: 'cassette' };
        guide.dataset.subject = next[guide.dataset.subject] || 'cassette';
    }

    function showGuide() {
        clearInterval(guideTimer);
        guide.dataset.state = '';
        if (!stream) {
            guide.hidden = true;
            return;
        }
        guide.hidden = false;
        guide.dataset.subject = 'none';
        guideTimer = setInterval(switchGuide, 8000);
    }

    function message(text, state = '') {
        status.textContent = text;
        status.dataset.state = state;
    }

    function preferredCamera() {
        try { return localStorage.getItem('preferredCameraId'); }
        catch { return null; }
    }

    function recentlyActivated() {
        try {
            const last = Number(sessionStorage.getItem('lastCameraActivated'));
            const age = Date.now() - last;
            return last > 0 && age >= 0 && age < 5 * 60 * 1000;
        } catch { return false; }
    }

    function rememberActivation() {
        try { sessionStorage.setItem('lastCameraActivated', String(Date.now())); }
        catch { /* Camera remains usable when storage is unavailable. */ }
    }

    function stopCamera(fadeGuide = false) {
        generation++;
        clearInterval(guideTimer);
        if (fadeGuide) {
            guide.dataset.state = 'fading';
        } else {
            guide.hidden = true;
            guide.dataset.state = '';
        }
        cancelAnimationFrame(frame);
        if (stream) stream.getTracks().forEach(track => track.stop());
        stream = null;
        video.hidden = true;
        video.srcObject = null;
        stop.hidden = true;
        picker.hidden = true;
        start.disabled = !reader || detected;
        start.hidden = detected;
    }

    function decode(source) {
        const pixels = source.getContext('2d').getImageData(0, 0, source.width, source.height).data;
        const buffer = reader._malloc(pixels.byteLength);
        try {
            reader.HEAPU8.set(pixels, buffer);
            return reader.readBarcodeFromPixmap(buffer, source.width, source.height, true, 'DXFilmEdge,ITF');
        } finally {
            reader._free(buffer);
        }
    }

    function confirm(code) {
        const text = code.text?.trim();
        const parameter = code.format === 'ITF' && /^\d{6}$/.test(text) ? 'dx_full'
            : code.format === 'DX Film Edge' && /^\d+-\d+(?:\/\d+[A-Za-z]?)?$/.test(text) ? 'dx_number' : null;
        if (!parameter || detected) return false;
        detected = true;
        stopCamera(true);
        canvas.hidden = false;
        success.hidden = false;
        navigator.vibrate?.(120);
        start.disabled = true;
        choose.disabled = true;
        message(`✓ Barcode found: ${text}. Searching…`, 'success');
        const url = new URL(scanner.dataset.searchUrl, window.location.href);
        url.searchParams.set(parameter, text);
        setTimeout(() => { window.location.href = url.href; }, 550);
        return true;
    }

    function scanFrame(now) {
        if (!stream || detected) return;
        if (video.readyState >= 2 && now - lastScan >= 150) {
            lastScan = now;
            // Preserve the camera aspect ratio and enough detail for film-edge codes.
            const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
            const width = Math.round(video.videoWidth * scale);
            const height = Math.round(video.videoHeight * scale);
            if (canvas.width !== width) canvas.width = width;
            if (canvas.height !== height) canvas.height = height;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            try {
                if (confirm(decode(canvas))) return;
            } catch {
                stopCamera();
                message('Could not read the camera image. Try choosing a photo or restarting the camera.', 'error');
                return;
            }
        }
        frame = requestAnimationFrame(scanFrame);
    }

    async function startCamera(deviceId, remember = false) {
        stopCamera();
        const attempt = generation;
        if (!navigator.mediaDevices?.getUserMedia) {
            showGuide();
            message('Camera unavailable in this browser. Choose a photo instead.', 'error');
            return;
        }
        start.disabled = true;
        start.hidden = true;
        stop.hidden = false;
        message('Starting camera…');
        try {
            const constraints = { width: { ideal: 1280 }, facingMode: { ideal: 'environment' } };
            if (deviceId) constraints.deviceId = { exact: deviceId };
            let nextStream;
            try {
                nextStream = await navigator.mediaDevices.getUserMedia({ video: constraints, audio: false });
            } catch (error) {
                if (error.name !== 'OverconstrainedError' || !deviceId || attempt !== generation) throw error;
                delete constraints.deviceId;
                nextStream = await navigator.mediaDevices.getUserMedia({ video: constraints, audio: false });
            }
            if (attempt !== generation) {
                nextStream.getTracks().forEach(track => track.stop());
                return;
            }
            stream = nextStream;
            video.srcObject = stream;
            await video.play();
            if (attempt !== generation) return;
            if (remember) rememberActivation();
            // Let the browser render the live stream at its own frame rate.
            // The hidden canvas is only used for barcode decoding.
            canvas.hidden = true;
            video.hidden = false;
            showGuide();
            message('Point the camera at the cassette barcode or the film roll…');
            frame = requestAnimationFrame(scanFrame);
            // Device labels become available after camera permission is granted.
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                if (attempt !== generation) return;
                selector.replaceChildren();
                const cameras = devices.filter(device => device.kind === 'videoinput');
                cameras.forEach((device, i) => {
                    const option = document.createElement('option');
                    option.value = device.deviceId;
                    option.textContent = device.label || `Camera ${i + 1}`;
                    selector.appendChild(option);
                });
                selector.value = stream.getVideoTracks()[0].getSettings().deviceId || '';
                picker.hidden = cameras.length < 2;
            } catch { /* Scanning remains available without a device picker. */ }
        } catch (error) {
            if (attempt !== generation) return;
            stopCamera();
            canvas.hidden = true;
            showGuide();
            message(error.name === 'NotAllowedError'
                ? 'Camera access was denied. Allow access and try again, or choose a photo.'
                : 'Could not start the camera. Choose a photo or try again.', 'error');
        }
    }

    start.addEventListener('click', () => startCamera(preferredCamera(), true));
    stop.addEventListener('click', () => {
        try { sessionStorage.removeItem('lastCameraActivated'); } catch { /* Optional storage. */ }
        stopCamera();
        canvas.hidden = true;
        showGuide();
        message('Camera stopped. Start it again or choose a photo.');
    });
    selector.addEventListener('change', () => {
        try { localStorage.setItem('preferredCameraId', selector.value); } catch { /* Optional preference. */ }
        startCamera(selector.value, true);
    });
    choose.addEventListener('click', () => input.click());
    input.addEventListener('change', async () => {
        const file = input.files?.[0];
        input.value = ''; // Allow retrying the same photo.
        if (!file || detected) return;
        stopCamera();
        const attempt = generation;
        choose.disabled = true;
        start.disabled = true;
        canvas.hidden = true;
        message('Reading your photo…');
        const url = URL.createObjectURL(file);
        try {
            const image = new Image();
            image.src = url;
            await image.decode();
            if (attempt !== generation) return;
            const scale = Math.min(1, 3000 / Math.max(image.naturalWidth, image.naturalHeight));
            canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
            canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
            ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
            canvas.hidden = false;
            if (!confirm(decode(canvas))) {
                message('No DX barcode found. Try a sharper photo, closer to the barcode and without reflections.', 'error');
            }
        } catch {
            if (attempt === generation) message('Could not read this photo. Try a JPEG, PNG or WebP image.', 'error');
        } finally {
            URL.revokeObjectURL(url);
            if (!detected) {
                choose.disabled = false;
                start.disabled = !reader;
            }
        }
    });
    window.addEventListener('pagehide', () => stopCamera());
    document.addEventListener('visibilitychange', () => {
        if (document.hidden && stream && !detected) {
            stopCamera();
            canvas.hidden = true;
            showGuide();
            message('Camera paused. Start it again to continue scanning.');
        }
    });

    function restoreScanner() {
        detected = false;
        success.hidden = true;
        start.disabled = false;
        start.hidden = false;
        choose.disabled = false;
        canvas.hidden = true;
        showGuide();
        message('Scan the cassette barcode or the film edge. Keep it sharp and well lit.');
        if (recentlyActivated()) startCamera(preferredCamera());
    }

    window.addEventListener('pageshow', event => {
        if (event.persisted && reader) restoreScanner();
    });

    Promise.resolve().then(() => ZXing()).then(instance => {
        reader = instance;
        restoreScanner();
    }).catch(() => {
        message('The barcode reader could not load. Reload the page to try again.', 'error');
    });
})();
