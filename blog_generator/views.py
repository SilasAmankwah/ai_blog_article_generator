from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import os
from dotenv import load_dotenv 
load_dotenv()
import json
#from pytube import YouTube
import assemblyai as aai
from groq import Groq
import yt_dlp
import requests
import time
from .models import BlogPost

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        try:
            print("Getting title...")
            title = yt_title(yt_link)
            print(f"Title: {title}")

            print("Getting transcription...")
            transcription = get_transcription(yt_link)
            print(f"Transcription: {transcription}")

            if not transcription:
                return JsonResponse({'error': 'Failed to get transcript'}, status=500)
            
           

            print("Generating blog...")
            blog_content = generate_blog_from_transcription(transcription)
            print(f"Blog: {blog_content}")

            new_blog_article = BlogPost.objects.create(
                user=request.user,
                youtube_title=title,
                youtube_link=yt_link,
                generated_content=blog_content,
            )
            new_blog_article.save()

            return JsonResponse({'content': blog_content})
        
            
        except Exception as e:
            print(f"EXACT ERROR: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
def yt_title(link):
    with yt_dlp.YoutubeDL({}) as ydl:
        info = ydl.extract_info(link, download=False)
        return info['title']


def download_audio(link):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(settings.MEDIA_ROOT, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'socket_timeout': 120,
        'retries': 10,
        'fragment_retries': 10,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=True)
        audio_file = os.path.join(
            settings.MEDIA_ROOT,
            f"{info['title']}.mp3"
        )
    
    # Verify file exists and is complete
    if not os.path.exists(audio_file):
        raise Exception(f"Audio file not found: {audio_file}")
    
    file_size = os.path.getsize(audio_file)
    print(f"Audio file size: {file_size} bytes")
    
    if file_size < 1000:
        raise Exception("Audio file too small - download may have failed")
    
    return audio_file



def get_transcription(link):
    audio_file = download_audio(link)
    
    headers = {"authorization": os.environ.get("22e56a0ca81d4d86a974acf92f3ab271")}
    
    # Upload the file
    with open(audio_file, "rb") as f:
        upload_response = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers=headers,
            data=f
        )
    
    print(f"Upload response: {upload_response.json()}")
    
    if "upload_url" not in upload_response.json():
        print(f"Upload failed: {upload_response.json()}")
        return None
        
    upload_url = upload_response.json()["upload_url"]
    
    # Request transcription
    transcript_response = requests.post(
    "https://api.assemblyai.com/v2/transcript",
    headers=headers,
    json={
        "audio_url": upload_url,
        "speech_models": ["universal-2"]
    }
)
    
    print(f"Transcript response: {transcript_response.json()}")
    result = transcript_response.json()
    
    if "id" not in result:
        return None
        
    transcript_id = result["id"]
    
    # Poll for completion
    while True:
        response = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
            headers=headers
        )
        result = response.json()
        if result["status"] == "completed":
            return result["text"]
        elif result["status"] == "error":
            return None
        time.sleep(3)

def generate_blog_from_transcription(transcription):
    client = Groq(api_key=os.environ.get("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"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": f"Based on this transcript, write a comprehensive blog article, write it based on the transcript, but don't make it look like a YouTube video, make it look like a proper blog article:\n\n{transcription}"
        }],
        max_tokens=1000
    )
    return response.choices[0].message.content.strip()
   

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('index')

def user_login(request):
    if request.method =='POST':
        username = request.POST['username']
        password = request.POST['password']

        user=authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            error_message = "Invalid username or password"
            return render(request, 'Login.html', {'error_message': error_message})

    return render(request, 'Login.html')

def user_signUp(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username=username, email=email, password=password)
                user.save()

                user = authenticate(request, username=username, password=password)

                login(request, user)

                return redirect('index')
            except:
                error_message = 'Error creating account'
                return render(request, 'signUp.html', {'error_message': error_message})
        else:
            error_message = 'Passwords do not match'
            return render(request, 'signUp.html', {'error_message': error_message})
        
    return render(request, 'signUp.html')

    

def user_logout(request):
    logout(request)
    return redirect('index')
