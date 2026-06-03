#https://www.youtube.com/watch?v=iM4Pz-9oyiE

from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

print("UPLOAD_DIR EXISTS:", UPLOAD_DIR.exists())

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_DIR)),
    name="uploads"
) 

@app.post('/uploadfile/')
async def create_upload_file(file_upload: UploadFile):

    data = await file_upload.read()
    save_to = UPLOAD_DIR / file_upload.filename
    print("UPLOAD_DIR:", UPLOAD_DIR)
    print("Saving to:", save_to)
    with open(save_to, 'wb') as f:
        f.write(data)

    print("File exists:", save_to.exists())
    return {"filename": file_upload.filename,
            "file_url": f"/uploads/{file_upload.filename}"}