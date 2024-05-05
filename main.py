from fastapi import FastAPI, Request, Form, status, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.auth.transport import requests
from google.cloud import firestore
from datetime import datetime
import google.oauth2.id_token
from google.auth.transport import requests
import re
import shutil
import os
from datetime import datetime
import traceback
import json
from typing import List
from starlette.status import HTTP_302_FOUND, HTTP_303_SEE_OTHER

app = FastAPI()

firestore_db = firestore.Client()
firebase_request_adapter = requests.Request()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")
token = None

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, error: str = None):
    id_token = request.cookies.get("token")
    error_message = error
    user_token = None
    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        
            user_id = user_token['user_id']
            user_query = firestore_db.collection('User').where('user_id', '==', user_id).limit(1).get()
            
            if not user_query:
                return RedirectResponse(url="/add_username", status_code=303)

        except ValueError as err:
            print("Error verifying Firebase ID token:", str(err))
            
            return RedirectResponse(url="/", status_code=303)  

    return templates.TemplateResponse('index.html', {'request': request, 'user_token': user_token, 'error_message': error_message})

@app.get("/add_username", response_class=HTMLResponse)
async def add_username(request: Request):
    return templates.TemplateResponse('add_username.html', {'request': request})

@app.post("/add_username", response_class=RedirectResponse)
async def add_username(request: Request, username: str = Form(...)):
    id_token = request.cookies.get("token")
    if not id_token:
        return RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)
    
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']
        
        user_collection = firestore_db.collection('User')
        username_query = user_collection.where('username', '==', username).stream()
        user_id_query = user_collection.where('user_id', '==', user_id).stream()

        if any(username_query):
            
            return RedirectResponse(url="/?error=Username+already+exists", status_code=HTTP_303_SEE_OTHER)

        if any(user_id_query):
            
            return RedirectResponse(url="/?error=User+already+has+a+username", status_code=HTTP_303_SEE_OTHER)

        user_data = {
            'username': username,
            'user_id': user_id
        }
        user_collection.add(user_data)

    except ValueError as err:
        print("Error verifying Firebase ID token:", str(err))
        return RedirectResponse(url="/", status_code=HTTP_302_FOUND)

    return RedirectResponse("/", status_code=HTTP_302_FOUND)

@app.get("/add_tweet", response_class=HTMLResponse)
async def add_tweet(request: Request):
    return templates.TemplateResponse('add_tweet.html', {'request': request})

@app.post("/add_tweet", response_class=RedirectResponse)
async def add_tweet(request: Request, content_type: str = Form(...), content: str = Form(None), content_image: UploadFile = File(None)):
    id_token = request.cookies.get("token")
    if not id_token:
        return RedirectResponse(url="/", status_code=303)

    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']

        user_doc_ref = firestore_db.collection('User').where('user_id', '==', user_id).get()
        if not user_doc_ref:
            return RedirectResponse(url="/?error=User+not+found", status_code=303)
        username = user_doc_ref[0].to_dict()['username'] 

        if content_type == "text":
            if len(content) > 140:
                return RedirectResponse(url="/?error=Content+too+long", status_code=303)
            content_data = content
            image_path = ""  
        elif content_type == "image":
            if not content_image:
                return RedirectResponse(url="/?error=No+image+uploaded", status_code=303)

            image_path = os.path.join("static/uploads", content_image.filename)
            with open(image_path, "wb") as image_file:
                shutil.copyfileobj(content_image.file, image_file)
            content_data = ""  

        tweet_data = {
            "user_id": user_id,
            "name": username,  
            "content": content_data,
            "image": image_path,
            "type": content_type,
            "date": datetime.now()
        }

        firestore_db.collection('Tweet').add(tweet_data)
        return RedirectResponse("/", status_code=302)

    except ValueError as err:
        print("Error:", str(err))
        return RedirectResponse(url="/", status_code=302)

@app.get("/search_username", response_class=HTMLResponse)
async def add_tweet(request: Request):
    return templates.TemplateResponse('search_username.html', {'request': request})

@app.post("/search_username", response_class=JSONResponse)
async def search_username(request: Request, username: str = Form(...)):
    search_input=username
    id_token = request.cookies.get("token")
    if not id_token:
        return JSONResponse(content={"message": "Unauthorized"}, status_code=401)

    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        normalized_input = search_input.strip().lower()
        query = firestore_db.collection('User')
        existing_users = query.stream()
        user_data = []
        for doc in existing_users:
            user = doc.to_dict()
            
            if normalized_input in user.get('username', '').lower():
                user['user_id'] = doc.id  
                user_data.append(user)
        if user_data:
            print(user_data)  
            return JSONResponse(content=user_data, status_code=200)
        else:
            return JSONResponse(content={"message": "No matching user found"}, status_code=404)

    except ValueError as err:
        print("Error verifying Firebase ID token:", str(err))
        return JSONResponse(content={"message": "Internal server error"}, status_code=500)
    
@app.get("/search_tweet", response_class=HTMLResponse)
async def search_tweet(request: Request):
    return templates.TemplateResponse('search_tweet.html', {'request': request})
    
from datetime import datetime

@app.post("/search_tweet", response_class=JSONResponse)
async def search_tweet(request: Request, search_input: str = Form(...)):
    id_token = request.cookies.get("token")
    if not id_token:
        return JSONResponse(content={"message": "Unauthorized"}, status_code=401)

    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        
        print("Search Input:", search_input)  
        
        normalized_input = search_input.strip().lower()
        
        query = firestore_db.collection('Tweet')
        existing_tweets = query.stream()

        tweet_data = []  
        
        for doc in existing_tweets:
            tweet = doc.to_dict()
            
            if 'date' in tweet and isinstance(tweet['date'], datetime):
                tweet['date'] = tweet['date'].isoformat()

            print("Fetched Tweet:", tweet)  
            
            if tweet.get('type') == 'text' and normalized_input in tweet.get('content', '').lower():
                tweet['tweet_id'] = doc.id  
                tweet_data.append(tweet)  

        if tweet_data:
            print(tweet_data) 
            return JSONResponse(content=tweet_data, status_code=200)
        else:
            return JSONResponse(content={"message": "No matching tweets found"}, status_code=404)

    except ValueError as err:
        print("Error verifying Firebase ID token:", str(err))
        return JSONResponse(content={"message": "Internal server error"}, status_code=500)

@app.get("/user_profile/{user_profile_name}", response_class=HTMLResponse)
async def user_profile(request: Request, user_profile_name: str):
    id_token = request.cookies.get("token")
    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            user_id = user_token['user_id']
        except ValueError as err:
            print(str(err))
            return RedirectResponse("/", status_code=HTTP_302_FOUND)
    else:
        user_id = None  

    user_query = firestore_db.collection('User').where('username', '==', user_profile_name).stream()
    user_data = [doc.to_dict() for doc in user_query]

    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    searched_user_id = user_data[0]['user_id']

    tweets_query = firestore_db.collection('Tweet').where('user_id', '==', searched_user_id).limit(10).stream()
    tweets_data = [tweet.to_dict() for tweet in tweets_query]

    tweets_data.sort(key=lambda x: x['date'], reverse=True)

    is_following = False
    if user_id:
        follow_query = firestore_db.collection('follows').where('follower', '==', user_id).where('following', '==', searched_user_id).stream()
        is_following = any(follow_query)

    return templates.TemplateResponse("user_profile.html", {
        "request": request,
        "user_data": user_data[0],
        "tweets": tweets_data,
        "is_following": is_following
    })

@app.get("/follow/{user_profile_id}", response_class=RedirectResponse)
async def follow(request: Request, user_profile_id: str):
    id_token = request.cookies.get("token")
    if not id_token:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']
    except ValueError as err:
        print(str(err))
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    usernames_collection = firestore_db.collection('User')

    user_query = usernames_collection.where('username', '==', user_profile_id).get()
    if not user_query:
        return RedirectResponse("/", status_code=status.HTTP_404_NOT_FOUND)  

    user_profile_data = user_query[0].to_dict()
    user_profile_user_id = user_profile_data.get('user_id')

    if not user_profile_user_id:
        return RedirectResponse("/", status_code=status.HTTP_404_NOT_FOUND)  

    follows_collection = firestore_db.collection('follows')

    follow_query = follows_collection.where('follower', '==', user_id).where('following', '==', user_profile_user_id).get()

    if follow_query:
        
        for doc in follow_query:
            follows_collection.document(doc.id).delete()
        message = "Unfollow successful"
    else:
        
        follow_data = {
            'follower': user_id,
            'following': user_profile_user_id,
            'date': datetime.utcnow()
        }
        follows_collection.add(follow_data)
        message = "Follow successful"

    return RedirectResponse(f"/user_profile/{user_profile_id}?message={message}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/timeline", response_class=HTMLResponse)
async def timeline(request: Request):
    id_token = request.cookies.get("token")
    if not id_token:
        return JSONResponse(content={"error": "No token provided"}, status_code=401)
    
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']

        follows_query = firestore_db.collection('follows').where('follower', '==', user_id).stream()
        following_users = [user_id] + [doc.to_dict()['following'] for doc in follows_query]  
        
        tweets = []
        for following_user in following_users:
            user_tweets_query = firestore_db.collection('Tweet').where('user_id', '==', following_user).stream()
            tweets.extend([tweet.to_dict() for tweet in user_tweets_query])

        sorted_tweets = sorted(tweets, key=lambda x: x['date'], reverse=True)
        
        timeline_tweets = sorted_tweets[:20]
        
        return templates.TemplateResponse("timeline.html", {"request": request, "timeline_tweets": timeline_tweets})

    except ValueError as err:
        print(str(err))
        return JSONResponse(content={"error": "Token verification failed"}, status_code=401)

@app.get("/my_tweets", response_class=HTMLResponse)
async def get_my_tweets(request: Request):
    id_token = request.cookies.get("token")
    if id_token:
        try:
            
            user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            user_id = user_token['user_id']

            
            tweets_query = firestore_db.collection('Tweet').where('user_id', '==', user_id).stream()
            tweets = [{
                "id": doc.id,  
                **doc.to_dict()
            } for doc in tweets_query]
            sorted_tweets = sorted(tweets, key=lambda x: x['date'], reverse=True)
            
            return templates.TemplateResponse("my_tweets.html", {"request": request, "tweets": sorted_tweets})
        except ValueError as err:
            print("Error verifying Firebase ID token:", str(err))
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    else:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    
@app.get("/edit/{document_id}", response_class=HTMLResponse)
async def edit_tweet(request: Request, document_id: str):
    id_token = request.cookies.get("token")
    if not id_token:
        return JSONResponse(content={"error": "No token provided"}, status_code=401)
    
    try:
       
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']

        tweet_ref = firestore_db.collection('Tweet').document(document_id)
        tweet_doc = tweet_ref.get()
        if not tweet_doc.exists:
            return JSONResponse(content={"error": "Tweet not found"}, status_code=404)

        tweet_data = tweet_doc.to_dict()

        if tweet_data['user_id'] != user_id:
            return JSONResponse(content={"error": "Unauthorized"}, status_code=403)
        
        print(tweet_data)

        return templates.TemplateResponse("edit_tweet.html", {
            "request": request,
            "tweet": tweet_data,
            "document_id": document_id
        })

    except ValueError as err:
        print("Error verifying Firebase ID token:", str(err))
        return JSONResponse(content={"error": "Invalid authentication credentials"}, status_code=401)
    
@app.post("/update_tweet/{document_id}")
async def update_tweet(request: Request, document_id: str, content_type: str = Form(...), content: str = Form(None), content_image: UploadFile = File(None)):
    id_token = request.cookies.get("token")
    if not id_token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']

        tweet_ref = firestore_db.collection('Tweet').document(document_id)
        tweet_doc = tweet_ref.get()
        if not tweet_doc.exists:
            return RedirectResponse(url="/", status_code=status.HTTP_404_NOT_FOUND, headers={"Content-Type": "application/json"})

        tweet_data = tweet_doc.to_dict()

        if tweet_data['user_id'] != user_id:
            return RedirectResponse(url="/", status_code=status.HTTP_403_FORBIDDEN)

        if tweet_data['type'] != content_type:
            
            if content_type == "image":
                if content_image:
                   
                    image_path = os.path.join("static/uploads", content_image.filename)
                    with open(image_path, "wb") as image_file:
                        shutil.copyfileobj(content_image.file, image_file)
                    
                    tweet_ref.update({
                        "content": "",  
                        "image": image_path,
                        "type": content_type,
                        "date": datetime.now()
                    })
                else:
                    raise HTTPException(status_code=400, detail="No image uploaded")

            elif content_type == "text":
                
                if tweet_data['image']:
                    os.remove(tweet_data['image'])
                
                tweet_ref.update({
                    "content": content,
                    "image": "",  
                    "type": content_type,
                    "date": datetime.now()
                })
        else:
            
            if content_type == "text":
                tweet_ref.update({
                    "content": content,
                    "date": datetime.now()
                })
            elif content_type == "image":
                if content_image:
                    image_path = os.path.join("static/uploads", content_image.filename)
                    with open(image_path, "wb") as image_file:
                        shutil.copyfileobj(content_image.file, image_file)
                    tweet_ref.update({
                        "image": image_path,
                        "date": datetime.now()
                    })
                else:
                    
                    pass

        return RedirectResponse(url="/my_tweets", status_code=status.HTTP_303_SEE_OTHER)

    except ValueError as err:
        print("Error verifying Firebase ID token:", str(err))
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
@app.get("/delete/{document_id}", response_class=RedirectResponse)
async def delete_tweet(request: Request, document_id: str):
    id_token = request.cookies.get("token")
    if not id_token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']

        tweet_ref = firestore_db.collection('Tweet').document(document_id)
        tweet_doc = tweet_ref.get()
        if not tweet_doc.exists:
            return JSONResponse(content={"error": "Tweet not found"}, status_code=404)
        
        tweet_data = tweet_doc.to_dict()

        if tweet_data['user_id'] != user_id:
            return JSONResponse(content={"error": "Unauthorized"}, status_code=403)


        tweet_ref.delete()

        if tweet_data['image']:
            image_path = tweet_data['image']
            os.remove(image_path)

        return RedirectResponse(url="/my_tweets", status_code=status.HTTP_303_SEE_OTHER)
    
    except ValueError as err:
        print("Error verifying Firebase ID token:", str(err))
        return JSONResponse(content={"error": "Invalid authentication credentials"}, status_code=401)