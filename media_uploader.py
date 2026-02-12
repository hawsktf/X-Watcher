import requests
import os

def upload_to_nostr_build(file_path):
    """
    Uploads an image to nostr.build.
    Returns the URL of the uploaded image or None if failed.
    """
    if not os.path.exists(file_path):
        print(f"  ❌ Media: File {file_path} not found.")
        return None

    print(f"  ☁️ Media: Uploading {os.path.basename(file_path)} to nostr.build...")
    
    url = "https://nostr.build/api/v2/upload/files"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file[]': f}
            # nostr.build V2 API often requires some headers or handles it simply
            # For public uploads, sometimes it's restricted. 
            # Let's try the simplest form first or check if they have a public route.
            # actually nostr.build might need an API key for V2, let's try V1 or void.cat
            response = requests.post(url, files=files, timeout=30)
            
        if response.status_code == 200:
            data = response.json()
            # Response structure for nostr.build V2 usually has a 'data' list
            if data.get('data') and len(data['data']) > 0:
                img_url = data['data'][0].get('url')
                print(f"  ✅ Media: Uploaded successfully! URL: {img_url}")
                return img_url
        
        print(f"  ❌ Media: Upload failed with status {response.status_code}: {response.text}")
        return None
    except Exception as e:
        print(f"  ❌ Media: Error during upload: {e}")
        return None

def upload_to_catbox(file_path):
    """Uploads to Catbox.moe"""
    if not os.path.exists(file_path): return None
    print(f"  ☁️ Media: Uploading {os.path.basename(file_path)} to catbox.moe...")
    url = "https://catbox.moe/user/api.php"
    try:
        with open(file_path, 'rb') as f:
            data = {'reqtype': 'fileupload'}
            files = {'fileToUpload': f}
            response = requests.post(url, data=data, files=files, timeout=30)
            
        if response.status_code == 200:
            img_url = response.text.strip()
            if img_url.startswith("http"):
                print(f"  ✅ Media: Uploaded successfully! URL: {img_url}")
                return img_url
        
        print(f"  ❌ Media: Catbox failed with status {response.status_code}")
        return None
    except Exception as e:
        print(f"  ❌ Media: Catbox error: {e}")
        return None

def upload_to_uguu(file_path):
    """Uploads to Uguu.se"""
    if not os.path.exists(file_path): return None
    print(f"  ☁️ Media: Uploading {os.path.basename(file_path)} to uguu.se...")
    url = "https://uguu.se/api.php?d=upload-tool"
    try:
        with open(file_path, 'rb') as f:
            files = {'files[]': f}
            response = requests.post(url, files=files, timeout=30)
            
        if response.status_code == 200:
            img_url = response.text.strip()
            if img_url.startswith("http"):
                print(f"  ✅ Media: Uploaded successfully! URL: {img_url}")
                return img_url
        
        print(f"  ❌ Media: Uguu failed with status {response.status_code}")
        return None
    except Exception as e:
        print(f"  ❌ Media: Uguu error: {e}")
        return None
def upload_to_void_cat(file_path):
    """Fallback uploader using void.cat"""
    if not os.path.exists(file_path): return None
    
    print(f"  ☁️ Media: Uploading {os.path.basename(file_path)} to void.cat...")
    url = "https://void.cat/upload"
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, files=files, timeout=30)
            
        if response.status_code == 200:
            data = response.json()
            file_id = data.get('id')
            if file_id:
                img_url = f"https://void.cat/d/{file_id}"
                print(f"  ✅ Media: Uploaded successfully! URL: {img_url}")
                return img_url
        
        print(f"  ❌ Media: void.cat failed with status {response.status_code}")
        return None
    except Exception as e:
        print(f"  ❌ Media: void.cat error: {e}")
        return None

def upload_to_pomf(file_path):
    """Uploads to pomf2.la"""
    if not os.path.exists(file_path): return None
    print(f"  ☁️ Media: Uploading {os.path.basename(file_path)} to pomf2.la...")
    url = "https://pomf2.la/upload.php"
    try:
        with open(file_path, 'rb') as f:
            files = {'files[]': f}
            response = requests.post(url, files=files, timeout=30)
            
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('files'):
                img_url = data['files'][0].get('url')
                print(f"  ✅ Media: Uploaded successfully! URL: {img_url}")
                return img_url
        
        print(f"  ❌ Media: pomf2.la failed with status {response.status_code}")
        return None
    except Exception as e:
        print(f"  ❌ Media: pomf2.la error: {e}")
        return None

def upload_to_0x0(file_path):
    """Uploads to 0x0.st"""
    if not os.path.exists(file_path): return None
    print(f"  ☁️ Media: Uploading {os.path.basename(file_path)} to 0x0.st...")
    url = "https://0x0.st"
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, files=files, timeout=30)
            
        if response.status_code == 200:
            img_url = response.text.strip()
            if img_url.startswith("http"):
                print(f"  ✅ Media: Uploaded successfully! URL: {img_url}")
                return img_url
        
        print(f"  ❌ Media: 0x0.st failed with status {response.status_code}")
        return None
    except Exception as e:
        print(f"  ❌ Media: 0x0.st error: {e}")
        return None

def upload_to_litterbox(file_path):
    """Uploads to Litterbox (Temporary hosting)"""
    if not os.path.exists(file_path): return None
    print(f"  ☁️ Media: Uploading {os.path.basename(file_path)} to litterbox.catbox.moe...")
    url = "https://litterbox.catbox.moe/resources/internals/api.php"
    try:
        with open(file_path, 'rb') as f:
            data = {'reqtype': 'fileupload', 'time': '1h'} # 1 hour is enough for verify
            files = {'fileToUpload': f}
            response = requests.post(url, data=data, files=files, timeout=30)
            
        if response.status_code == 200:
            img_url = response.text.strip()
            if img_url.startswith("http"):
                print(f"  ✅ Media: Uploaded successfully! URL: {img_url}")
                return img_url
        
        print(f"  ❌ Media: Litterbox failed with status {response.status_code}")
        return None
    except Exception as e:
        print(f"  ❌ Media: Litterbox error: {e}")
        return None

def upload_media(file_path):
    """Try multiple providers for robustness."""
    # 1. Try Uguu.se (Usually very reliable for valid images)
    url = upload_to_uguu(file_path)
    if url: return url

    # 2. Try Catbox.moe
    url = upload_to_catbox(file_path)
    if url: return url
    
    # 3. Try Litterbox
    url = upload_to_litterbox(file_path)
    if url: return url
    
    # 4. Try pomf2.la
    url = upload_to_pomf(file_path)
    if url: return url
    
    # 5. Try void.cat
    url = upload_to_void_cat(file_path)
    if url: return url
    
    # 6. Try nostr.build (requires NIP-98 now)
    url = upload_to_nostr_build(file_path)
    
    return url

if __name__ == "__main__":
    # Test upload
    pass
