"""
    1. Record audio through their microphone
    2. Transcribe the audio to text
    3. Generate an image prompt using the Groq Llama3 model
    4. Generate an image using the Replicate.ai Flux model
    5. Display the generated image
    6. Download the generated image
    The application uses DaisyUI and Tailwind CSS for styling, providing a dark mode interface. The layout is responsive and should work well on both desktop and mobile devices.
Note: You may need to adjust some parts of the code depending on the specific APIs and models you're using, as well as any security considerations for your deployment environment.

"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import speech_recognition as sr
from groq import Groq
import replicate
import os
import aiohttp
import aiofiles
import time
from dotenv import load_dotenv
load_dotenv()
from .utils import text_to_speech, save_audio
from PIL import Image
import io
import base64
import base64


# Function to encode the image
def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize Groq client with the API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in the environment variables")
groq_client = Groq(api_key=GROQ_API_KEY)

class AudioData(BaseModel):
    audio_data: str

class ImagePrompt(BaseModel):
    prompt: str

class PromptRequest(BaseModel):
    text: str

# Add this new model
class FreeImagePrompt(BaseModel):
    prompt: str
    image_path: str

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/transcribe")
async def transcribe_audio(audio_data: AudioData):
    try:
        # Save the audio data to a file
        audio_file = save_audio(audio_data.audio_data)

        # Transcribe the audio
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_file) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)

        return JSONResponse(content={"text": text})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/generate_prompt")
async def generate_prompt(prompt_request: PromptRequest):
    try:
        text = prompt_request.text
        # Use Groq to generate a new prompt
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a creative assistant that generates prompts for realistic image generation."},
                {"role": "user", "content": f"Generate a detailed prompt for a realistic image based on this description: {text}.The prompt should be clear and detailed in no more than 200 words."}
            ],
            model="llama-3.1-70b-versatile",
            max_tokens=256
        )
        generated_prompt = response.choices[0].message.content
        print(f"tweaked prompt:{generated_prompt}")
        return JSONResponse(content={"prompt": generated_prompt})
    except Exception as e:
        print(f"Error generating prompt: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/generate_image")
async def generate_image(image_prompt: ImagePrompt):
    try:
        prompt = image_prompt.prompt
        print(f"Received prompt: {prompt}")

        # Use Replicate to generate an image
        output = replicate.run(
            "black-forest-labs/flux-1.1-pro",
            input={
                "prompt": prompt,
                "aspect_ratio": "1:1",
                "output_format": "jpg",
                "output_quality": 80,
                "safety_tolerance": 2,
                "prompt_upsampling": True
            }
        )
        
        print(f"Raw output: {output}")
        print(f"Output type: {type(output)}")
        
        # Convert the FileOutput object to a string
        image_url = str(output)
        
        print(f"Generated image URL: {image_url}")
        
        return JSONResponse(content={"image_url": image_url})
    except Exception as e:
        print(f"Error generating image: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download_image")
async def download_image(image_url: str):
    try:
        # Create Output folder if it doesn't exist
        output_folder = "Output"
        os.makedirs(output_folder, exist_ok=True)

        # Generate a unique filename
        filename = f"generated_image_{int(time.time())}.jpg"
        filepath = os.path.join(output_folder, filename)

        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(filepath, mode='wb') as f:
                        await f.write(await resp.read())

        # Return the filepath and filename
        return JSONResponse(content={
            "filepath": filepath,
            "filename": filename
        })
    except Exception as e:
        print(f"Error downloading image: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

class StoryRequest(BaseModel):
    filepath: str
    filename: str

@app.post("/generate_story_from_image")
async def generate_story_from_image(content: StoryRequest):
    try:
        image_path = content.filepath
        print(f"Image path: {image_path}")
        # Check if the file exists
        if not os.path.exists(image_path):
            raise HTTPException(status_code=400, detail="Image file not found")

        # Getting the base64 string
        base64_image = encode_image(image_path)

        client = Groq()

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Generate a clear,concise,meaningful and engaging cover story for a highly acclaimed leisure magazine based on the image provided. The story should keep the audience glued and engaged and the story should bewithin 200 words."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            model="llava-v1.5-7b-4096-preview",
        )

        story = chat_completion.choices[0].message.content
        print(f"Generated story: {story}")
        return JSONResponse(content={"story": story})
    except Exception as e:
        print(f"Error generating story from the image: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download/{filename}")
async def serve_file(filename: str):
    file_path = os.path.join("Output", filename)
    return FileResponse(file_path, filename=filename)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)