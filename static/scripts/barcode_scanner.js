var zxing = ZXing().then(function (instance) {
    zxing = instance; // this line is supposedly not required but with current emsdk it is :-/
});

const cameraSelector = document.getElementById("cameraSelector");
const format = document.getElementById("dxformat");
const mode = document.getElementById("mode");
const canvas = document.getElementById("barcodescancanvas");
const enableimg = document.getElementById("barcodescanenableimg");
const resultElement = document.getElementById("result");
let videostreamstarted = false;

const ctx = canvas.getContext("2d", { willReadFrequently: true });
const video = document.createElement("video");
video.setAttribute("id", "video");
video.setAttribute("width", canvas.width);
video.setAttribute("height", canvas.height);
video.setAttribute("autoplay", "");
canvas.appendChild(video);
let lastDetectedCode = null;

function readBarcodeFromCanvas(canvas, format, mode) {
    var imgWidth = canvas.width;
    var imgHeight = canvas.height;
    var imageData = canvas.getContext('2d').getImageData(0, 0, imgWidth, imgHeight);
    var sourceBuffer = imageData.data;

    if (zxing != null) {
        var buffer = zxing._malloc(sourceBuffer.byteLength);
        zxing.HEAPU8.set(sourceBuffer, buffer);
        var result = zxing.readBarcodeFromPixmap(buffer, imgWidth, imgHeight, mode, format);
        zxing._free(buffer);
        return result;
    } else {
        return { error: "ZXing not yet initialized" };
    }
}

function drawResult(code) {
    ctx.beginPath();
    ctx.lineWidth = 4;
    ctx.strokeStyle = "red";
    with (code.position) {
        ctx.moveTo(topLeft.x, topLeft.y);
        ctx.lineTo(topRight.x, topRight.y);
        ctx.lineTo(bottomRight.x, bottomRight.y);
        ctx.lineTo(bottomLeft.x, bottomLeft.y);
        ctx.lineTo(topLeft.x, topLeft.y);
        ctx.stroke();
    }
}

function escapeTags(htmlStr) {
    return htmlStr.replace(/&/g, "&amp;").replace(/</g , "&lt;").replace( />/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

const processFrame = function () {
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const code = readBarcodeFromCanvas(canvas, format.value, mode.value === 'true');
    if (code.format) {
        const fullCode = `${code.format}:${code.text}`;
        if (fullCode !== lastDetectedCode) {
            lastDetectedCode = fullCode;
            resultElement.innerText = code.format + ": " + escapeTags(code.text);
            drawResult(code)
            if (code.format === "ITF") {
                window.location.href = "search?dx_full=" + encodeURIComponent(code.text);
            } else if (code.format === "DXFilmEdge") {
                window.location.href = "search?dx_number=" + encodeURIComponent(code.text);
            }
        }
    }
    requestAnimationFrame(processFrame);
};

const updateVideoStream = function (deviceId) {
    canvas.style.display = "";
    enableimg.style.display = "none";
    // To ensure the camera switch, it is advisable to free up the media resources
    if (video.srcObject) video.srcObject.getTracks().forEach(track => track.stop());

    navigator.mediaDevices
        .getUserMedia({ video: { facingMode: {"exact": deviceId} }, audio: false })
        .then(function (stream) {
            video.srcObject = stream;
            video.setAttribute("playsinline", true); // required to tell iOS safari we don't want fullscreen
            video.play();
            processFrame();
        })
        .catch(function (error) {
            console.error("Error accessing camera:", error);
        });
};

enableimg.addEventListener("click", function () {
    if (!videostreamstarted){
        videostreamstarted = true;
        updateVideoStream(cameraSelector.value);
    }
});

cameraSelector.addEventListener("change", function () {
    if (!videostreamstarted){
        videostreamstarted = true;
    }
    updateVideoStream(this.value);
});
