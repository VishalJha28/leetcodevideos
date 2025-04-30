import requests
from datetime import date
from langchain_community.chat_models import ChatGooglePalm
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import ffmpeg
import tempfile

load_dotenv()  # Load environment variables from .env file

class LeetCodeVideoGenerator:
    def __init__(self):
        google_api_key = os.getenv("GOOGLE_API_KEY")
        youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        if google_api_key:
            print("google api received")
        else:
            print("api key for google not found")
        if youtube_api_key:
            print("youtube api received")

        self.llm = ChatGooglePalm(google_api_key=google_api_key, temperature=0.7)
        self.youtube_api_key = youtube_api_key
        self.leetcode_endpoint = "https://leetcode.com/graphql"

    def fetch_easy_problems(self):
        query = """
            query {
              problemsetQuestionListV2(
                categorySlug: "",
                limit: 1000,
                skip: 0
              ) {
                questions {
                  title
                  titleSlug
                  questionFrontendId
                }
              }
            }
        """
        headers = {
            "Content-Type": "application/json",
        }
        response = requests.post(self.leetcode_endpoint, json={'query': query}, headers=headers)
        data = response.json()
        return data['data']['problemsetQuestionListV2']['questions']

    def get_today_problem(self, problems):
        today = date(2025, 4, 23)
        index = (today - date(2025, 1, 1)).days % len(problems)
        return problems[index]

    def generate_script(self, title, description):
        prompt = PromptTemplate(
            input_variables=["title", "description"],
            template="""
            Create a concise, engaging 1-minute YouTube Shorts script for the LeetCode problem titled "{title}". 
            Begin with a hook, explain the problem briefly, outline the optimal approach, and conclude with a call-to-action.
            Problem Description: {description}
            """
        )
        chain = LLMChain(llm=self.llm, prompt=prompt)
        return chain.run(title=title, description=description)

    def generate_video(self, script, output_path="short_video.mp4"):
        lines = [line.strip() for line in script.split("\n") if line.strip()]
        temp_dir = tempfile.mkdtemp()
        image_paths = []

        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)

        for idx, line in enumerate(lines):
            img = Image.new('RGB', (720, 1280), color='black')
            draw = ImageDraw.Draw(img)
            w, h = draw.textsize(line, font=font)
            draw.text(((720 - w) / 2, (1280 - h) / 2), line, fill="white", font=font)
            img_path = os.path.join(temp_dir, f"frame_{idx:03d}.png")
            img.save(img_path)
            image_paths.append(img_path)

        (
            ffmpeg
            .input(f'{temp_dir}/frame_%03d.png', framerate=1)
            .output(output_path, vcodec='libx264', pix_fmt='yuv420p', vf='scale=720:1280', crf=23, preset='ultrafast')
            .run()
        )

        return output_path

    def upload_to_youtube(self, video_path, title):
        youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": f"Quick 1-minute guide to solving {title} on LeetCode. Subscribe for more coding tips!",
                    "tags": ["LeetCode", "coding interview", "shorts", "python", "algorithms"],
                    "categoryId": "27"
                },
                "status": {
                    "privacyStatus": "public",
                    "madeForKids": False
                }
            },
            media_body=MediaFileUpload(video_path)
        )
        response = request.execute()
        return f"https://youtube.com/watch?v={response['id']}"

    def run(self):
        print("[INFO] Fetching LeetCode problems...")
        problems = self.fetch_easy_problems()
        problem = self.get_today_problem(problems)
        print(f"[INFO] Selected Problem: {problem['title']}")

        description = f"Problem ID {problem['questionFrontendId']} - {problem['title']}"
        print("[INFO] Generating video script...")
        script = self.generate_script(problem['title'], description)

        print("[INFO] Creating video...")
        video_path = self.generate_video(script)

        print("[INFO] Uploading video to YouTube...")
        youtube_url = self.upload_to_youtube(video_path, f"LeetCode Easy: {problem['title']}")
        print(f"[SUCCESS] Video uploaded: {youtube_url}")

# Example usage:
generator = LeetCodeVideoGenerator()
generator.run()
