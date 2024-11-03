let mediaRecorder;
let audioChunks = [];

const startRecordingButton = document.getElementById('startRecording');
const stopRecordingButton = document.getElementById('stopRecording');
const recordingStatus = document.getElementById('recordingStatus');
const transcription = document.getElementById('transcription');
const generatePromptButton = document.getElementById('generatePrompt');
const generatedPrompt = document.getElementById('generatedPrompt');
const generateImageButton = document.getElementById('generateImage');
const generatedImage = document.getElementById('generatedImage');
const downloadLink = document.getElementById('downloadLink');
const generateStoryButton = document.getElementById('generateStory');
const generatedStory = document.getElementById('generatedStory');

startRecordingButton.addEventListener('click', startRecording);
stopRecordingButton.addEventListener('click', stopRecording);
generatePromptButton.addEventListener('click', generatePrompt);
generateImageButton.addEventListener('click', generateImage);
generateStoryButton.addEventListener('click', generateStory);

async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
    };

    mediaRecorder.onstop = sendAudioToServer;

    mediaRecorder.start();
    startRecordingButton.disabled = true;
    stopRecordingButton.disabled = false;
    recordingStatus.textContent = 'Recording...';
}

function stopRecording() {
    mediaRecorder.stop();
    startRecordingButton.disabled = false;
    stopRecordingButton.disabled = true;
    recordingStatus.textContent = 'Recording stopped.';
}

async function sendAudioToServer() {
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
    const reader = new FileReader();
    reader.readAsDataURL(audioBlob);
    reader.onloadend = async () => {
        const base64Audio = reader.result;
        const response = await fetch('/transcribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ audio_data: base64Audio }),
        });
        const data = await response.json();
        transcription.textContent = `Transcription: ${data.text}`;
        generatePromptButton.disabled = false;
    };
    audioChunks = [];
}

async function generatePrompt() {
    const text = transcription.textContent.replace('Transcription: ', '');
    const response = await fetch('/generate_prompt', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: text }),
    });
    const data = await response.json();
    generatedPrompt.textContent = `Generated Prompt: ${data.prompt}`;
    generateImageButton.disabled = false;
}

async function generateImage() {
    const prompt = generatedPrompt.textContent.replace('Generated Prompt: ', '');
    const response = await fetch('/generate_image', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt: prompt }),
    });
    const data = await response.json();
    generatedImage.src = data.image_url;
    
    // Download the image and get the filepath
    const downloadResponse = await fetch(`/download_image?image_url=${encodeURIComponent(data.image_url)}`);
    const downloadData = await downloadResponse.json();
    
    // Store the filepath and filename for later use
    generatedImage.dataset.filepath = downloadData.filepath;
    generatedImage.dataset.filename = downloadData.filename;

    // Set up the download link
    downloadLink.href = `/download/${downloadData.filename}`;
    downloadLink.download = downloadData.filename;
    downloadLink.style.display = 'inline-block';
}

async function generateStory() {
    const imagePath = generatedImage.dataset.filepath;
    const filename = generatedImage.dataset.filename;
    
    if (!imagePath || !filename) {
        generatedStory.textContent = "Error: Please generate an image first.";
        return;
    }

    try {
        const response = await fetch('/generate_story_from_image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ filepath: imagePath, filename: filename }),
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // Display the generated story
        generatedStory.textContent = data.story;
        
        // Make sure the story container is visible
        document.getElementById('storyContainer').style.display = 'block';
    } catch (error) {
        console.error('Error:', error);
        generatedStory.textContent = `Error: ${error.message}`;
    }
}

// Modify the download link click event
downloadLink.addEventListener('click', async (event) => {
    event.preventDefault();
    const response = await fetch(downloadLink.href);
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = response.headers.get('Content-Disposition').split('filename=')[1];
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
});