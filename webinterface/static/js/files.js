function initializeProgress(numFiles) {
    document.getElementById("progress-bar").style.width = "0%";
    uploadProgress = []
    for (let i = numFiles; i > 0; i--) {
        uploadProgress.push(0)
    }
}

function updateProgress(fileNumber, percent) {
    uploadProgress[fileNumber] = percent
    let total = uploadProgress.reduce((tot, curr) => tot + curr, 0) / uploadProgress.length
    document.getElementById("progress-bar").style.width = total + "%";
    if (total >= 100 || total <= 0) {
        document.getElementById("progress-bar-group").classList.add("hidden");
    } else {
        document.getElementById("progress-bar-group").classList.remove("hidden");
    }
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;

    handleFiles(files)
}

function handleFiles(files) {
    document.getElementById("gallery").innerHTML = "";
    files = [...files]
    initializeProgress(files.length)
    files.forEach(uploadFile)
    files.forEach(previewFile)
}

function previewFile(file) {
    let reader = new FileReader()
    reader.readAsDataURL(file)

    reader.onloadend = function () {
        const name = document.createElement('div');
        name.setAttribute("id", file.name);
        name.innerHTML = file.name;
        name.className = "flex";
        document.getElementById('gallery').appendChild(name);
    }
}

function uploadFile(file, i) {
    const url = '/upload';
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    xhr.open('POST', url, true)
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest')

    // Update progress (can be used to show progress indicator)
    xhr.upload.addEventListener("progress", function (e) {
        updateProgress(i, (e.loaded * 100.0 / e.total) || 100)
    })

    xhr.addEventListener('readystatechange', function () {
        if (xhr.readyState === 4 && xhr.status === 200) {
            let response = JSON.parse(this.responseText);

            updateProgress(i, 100);

            if (response.success === true) {
                clearTimeout(get_songs_timeout);
                get_songs_timeout = setTimeout(function () {
                    get_songs();
                }, 2000);
                document.getElementById(response["song_name"]).innerHTML += "<svg xmlns=\"http://www.w3.org/2000/svg\" class=\"h-6 w-6 ml-2 text-green-400\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">\n" +
                    "  <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M5 13l4 4L19 7\" />\n" +
                    "</svg>";
            } else {
                document.getElementById(response["song_name"]).innerHTML += "<svg xmlns=\"http://www.w3.org/2000/svg\" class=\"h-6 w-6 ml-2 text-red-500\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">\n" +
                    "  <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M6 18L18 6M6 6l12 12\" />\n" +
                    "</svg>" + "<div class='text-red-400'>" + response.error + "</div>";
            }
        }
    })
    formData.append('file', file)
    xhr.send(formData)
}