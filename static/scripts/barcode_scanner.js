var zxing = ZXing().then(function (instance) {
    zxing = instance; // this line is supposedly not required but with current emsdk it is :-/
});

const cameraSelector = document.getElementById("cameraSelector");
const format = document.getElementById("dxformat");
const tryHarder = 'true'; // tryHarder in wasm: tryHarder + tryRotate + tryInvert
const canvas = document.getElementById("barcodescancanvas");
const enableimg = document.getElementById("barcodescanenableimg");
const resultElement = document.getElementById("result");
let videostreamstarted = false;
let currentStream = null;
let scanningEnabled = true;

const ctx = canvas.getContext("2d", { willReadFrequently: true });
const video = document.createElement("video");
video.setAttribute("id", "video");
video.setAttribute("width", canvas.width);
video.setAttribute("height", canvas.height);
video.setAttribute("autoplay", "");
canvas.appendChild(video);

function readBarcodeFromCanvas(canvas, format, tryHarder) {
    var imgWidth = canvas.width;
    var imgHeight = canvas.height;
    var imageData = canvas.getContext('2d').getImageData(0, 0, imgWidth, imgHeight);
    var sourceBuffer = imageData.data;

    if (zxing != null) {
        var buffer = zxing._malloc(sourceBuffer.byteLength);
        zxing.HEAPU8.set(sourceBuffer, buffer);
        var result = zxing.readBarcodeFromPixmap(buffer, imgWidth, imgHeight, tryHarder, format);
        zxing._free(buffer);
        return result;
    } else {
        return { error: "ZXing not yet initialized" };
    }
}

function drawResult(code) {
    with (code.position) {
        ctx.font = "bold 28px 'Open Sans', sans-serif";
        ctx.strokeStyle = "black";
        ctx.lineWidth = 4;
        // Avoid the text beoing out of the canvas (300 x 225)
        barcodeX = (topLeft.x + topRight.x + bottomLeft.x + bottomRight.x) / 4;
        barcodeY = (topLeft.y + topRight.y + bottomLeft.y + bottomRight.y) / 4;
        x = Math.min(215, Math.max(85, barcodeX));
        y = Math.min(200, Math.max(25, barcodeY));
        text = code.text
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.strokeText(text, x, y);
        ctx.fillStyle = "#fefefe"
        ctx.fillText(text, x, y)
    }
}

function escapeTags(htmlStr) {
    return htmlStr.replace(/&/g, "&amp;").replace(/</g , "&lt;").replace( />/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function temporaryDisableScanning(){
    scanningEnabled = false;
    setTimeout(function () {
        scanningEnabled = true;
    }, 1000);
}

const processFrame = function () {
    if (scanningEnabled === true){
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const code = readBarcodeFromCanvas(canvas, format.value, tryHarder === 'true');
    if (code.format) {
            temporaryDisableScanning()
            resultElement.innerText = code.format + ": " + escapeTags(code.text);
            drawResult(code)
            setTimeout(function () {
            if (code.format === "ITF") {
                window.location.href = "search?dx_full=" + encodeURIComponent(code.text);
            } else if (code.format === "DXFilmEdge") {
                window.location.href = "search?dx_number=" + encodeURIComponent(code.text);
            }
            }, 500);
    }
}
    requestAnimationFrame(processFrame);
};

const updateVideoStream = function (deviceId) {
    console.log("call updateVideoStream: " + deviceId)
    console.log("currentStream: " + currentStream);


    canvas.style.display = "";
    enableimg.style.display = "none";

    if (currentStream) {
        // Stop all tracks when switching or stopping the camera
        currentStream.getTracks().forEach(track => track.stop());
    }

    navigator.mediaDevices
        .getUserMedia({ video: {facingMode: "environment", "deviceId": deviceId }, audio: false })
        .then(function (stream) {
            currentStream = stream;
            video.srcObject = stream;
            video.setAttribute("playsinline", true); // required to tell iOS safari we don't want fullscreen
            video.play();
            processFrame();
            console.log("currentStream: " + currentStream);
        })
        .catch(function (error) {
            console.error("Error accessing camera:", error);
        });
};

function onCameraActivated(){
    sessionStorage.setItem('lastCameraActivated', Date.now().toString());
}

function isCameraRecentlyActivated() {
    const last = sessionStorage.getItem('lastCameraActivated');
    if (!last) return false;

    const lastTimestamp = parseInt(last, 10);
    const now = Date.now();
    const timeout = 5 * 60 * 1000; // 5 minutes

    if (now - lastTimestamp < timeout) {
        return true;
    } else {
        return false;
    }
}

function activateCamera(deviceId = null){
    onCameraActivated();
    if (!videostreamstarted){
        videostreamstarted = true;
        if (deviceId === null){
            updateVideoStream(cameraSelector.value);
        }
        else{
            updateVideoStream(deviceId);
        }
    }
}

enableimg.addEventListener("click", function () {
    activateCamera();
});

cameraSelector.addEventListener("change", function () {
    onCameraActivated();
    const selectedDeviceId = this.value;
    localStorage.setItem("preferredCameraId", selectedDeviceId);
    if (!videostreamstarted){
        videostreamstarted = true;
    }
    updateVideoStream(this.value);
});

if (!navigator.mediaDevices?.enumerateDevices) {
    console.log("enumerateDevices() not supported.");
  } else {
    // List cameras and microphones.
    const savedDeviceId = localStorage.getItem("preferredCameraId");

    navigator.mediaDevices
      .enumerateDevices()
      .then((devices) => {
        let audioSource = null;
        let videoSource = null;
  
        devices.forEach((device) => {
          if (device.kind === "audioinput") {
            audioSource = device.deviceId;
          } else if (device.kind === "videoinput") {
            videoSource = device.deviceId;
            const option = document.createElement("option");
            option.value = device.deviceId;
            option.text = device.label;
            cameraSelector.add(option, null);
            if (option.value === savedDeviceId){
                option.selected = true;
            }
            console.log(device)
          }
        });
      })
      .catch((err) => {
        console.error(`${err.name}: ${err.message}`);
      });
  }

if (isCameraRecentlyActivated()){
    const savedDeviceId = localStorage.getItem("preferredCameraId");
    activateCamera(savedDeviceId);
}
