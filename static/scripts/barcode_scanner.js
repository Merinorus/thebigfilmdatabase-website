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
let currentStream = null;


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

// function getDevices() {
//     try {
//       // Get all devices (audio & video)
//       const devices = navigator.mediaDevices.enumerateDevices();
      
//       // Filter for video input devices (cameras)
//       return devices.filter(device => device.kind === "videoinput");
//     } catch (err) {
//       console.error("Error accessing devices:", err);
//       return [];
//     }
//   }

// function populateCameraOptions(videoDevices) {
// // Clear the previous camera options
// cameraSelector.innerHTML = "";

// // Populate the dropdown with available video devices (cameras)
// videoDevices.forEach(device => {
//     const option = document.createElement("option");
//     option.value = device.deviceId;
//     option.textContent = device.label || `Camera ${cameraSelector.length + 1}`;
//     cameraSelector.appendChild(option);
// });

// // Trigger the camera on the first device
// if (videoDevices.length > 0) {
//     cameraSelector.value = videoDevices[0].deviceId;
//     startCamera(videoDevices[0].deviceId);
// }
// }

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

if (!navigator.mediaDevices?.enumerateDevices) {
    console.log("enumerateDevices() not supported.");
  } else {
    // List cameras and microphones.
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
            console.log(device)
          }
        });
        //sourceSelected(audioSource, videoSource);
      })
      .catch((err) => {
        console.error(`${err.name}: ${err.message}`);
      });
  }

// async function sourceSelected(audioSource, videoSource) {
// const constraints = {
//     audio: { deviceId: audioSource },
//     video: { deviceId: videoSource },
// };
// const stream = await navigator.mediaDevices.getUserMedia(constraints);
// }

// // Fetch video devices (cameras)
// navigator.mediaDevices.getUserMedia({ video: true });
// const videoDevices = getDevices();
// populateCameraOptions(videoDevices);