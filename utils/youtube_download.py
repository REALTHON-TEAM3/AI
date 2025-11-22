from pytubefix import YouTube
import os
import time
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def download_youtube(url: str) -> str | None:
    """Downloads a YouTube video and returns the file path."""
    logger.info(f"Starting download for YouTube video from: {url}")
    try:
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        if not stream:
            logger.error("No suitable progressive mp4 stream found.")
            return None
        
        file_path = stream.download(output_path="./videos")
        logger.info(f"Video downloaded successfully to: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"An error occurred during YouTube download: {e}")
        raise

def recog_video(prompt: str, url: str, model: genai.GenerativeModel, generation_config: dict) -> str:
    """
    Downloads a video, sends it to Gemini, and returns the full, concatenated response.
    Cleans up the downloaded file afterwards.
    """
    file_path = None
    uploaded_file = None
    try:
        file_path = download_youtube(url)
        if not file_path:
            raise ValueError("Failed to download video.")

        logger.info(f"Uploading file to Gemini: {file_path}")
        # Wait until the file is usable
        for _ in range(5):
            try:
                uploaded_file = genai.upload_file(path=file_path)
                break
            except Exception as e:
                logger.warning(f"File upload failed, retrying... Error: {e}")
                time.sleep(2)
        
        if not uploaded_file:
            raise ValueError("Failed to upload file to Gemini after multiple retries.")
            
        logger.info(f"File uploaded successfully: {uploaded_file.name}")

        # [추가] 파일 처리가 완료될 때까지 대기 (ACTIVE 상태 확인)
        while True:
            file = genai.get_file(uploaded_file.name)
            if file.state.name == "ACTIVE":
                logger.info("File is ACTIVE and ready for processing.")
                break
            elif file.state.name == "FAILED":
                raise ValueError("File processing failed on Gemini server.")
            
            logger.info("Waiting for file processing...")
            time.sleep(2)

        # Make the Gemini API call
        contents = [prompt, uploaded_file]
        logger.info("Generating content with Gemini...")
        responses = model.generate_content(contents, stream=True, generation_config=generation_config)
        
        # Concatenate all parts of the streamed response
        full_response = "".join(response.text for response in responses)
        
        logger.info("Finished generating content from Gemini.")
        return full_response.strip()

    finally:
        # Clean up the files
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Successfully deleted video file: {file_path}")
            except OSError as e:
                logger.error(f"Error deleting video file {file_path}: {e}")
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
                logger.info(f"Successfully deleted uploaded file from Gemini: {uploaded_file.name}")
            except Exception as e:
                logger.error(f"Error deleting uploaded file {uploaded_file.name} from Gemini: {e}")
