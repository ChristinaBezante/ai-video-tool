import '../styles/proxeiro.css'
import React,{useRef, useState} from 'react';
import axios from 'axios';  ///do in terminal npm install axios
import { CloudUpload, MessageCircle, ChevronRight, LoaderCircle, CheckCircle2 } from 'lucide-react';
//pip install "fastapi[standard]"
//to run fastapi dev main.py
//npm i video.js
import VideoJSPlayer from './VideoJSPlayer';
import ChatBot from './Chatbot.jsx'

const Proxeiro = () => {

    const [file, setFile] = useState(null);
    const [uploadProgress, setUploadProgres] = useState(0);
    const [uploadedFileURL, setUploadedFileURL] = useState(null);
    const [uploadError, setUploadError] = useState('');
    const [isUploading, setIsUploading] = useState(false);

    const playerRef = React.useRef(null);
    const inputRef = useRef(null);

    const uploadVideo = async (fileToUpload) => {
        const url = 'http://localhost:8000/uploadfile/';
        const formData = new FormData();
        formData.append('file_upload', fileToUpload);
        formData.append('filename', fileToUpload.name);

        try{
            setIsUploading(true);
            setUploadError('');
            const config = {
                onUploadProgress: progressEvent => {
                    const total = progressEvent.total || 1;
                    const percentCompleted = Math.round((progressEvent.loaded * 100) / total);
                    setUploadProgres(percentCompleted);
                }
            }
            const response = await axios.post(url, formData, config);

            // Add a cache-busting query so replacing an existing filename shows the new video.
            const fileUrl = `http://localhost:8000${response.data.file_url}?t=${Date.now()}`;
            setUploadedFileURL(fileUrl);
            setUploadProgres(100);
            console.log(response.data);
            console.log(response.data.file_url);
        }catch(error){
            setUploadError('Upload failed. Check that the FastAPI backend is running and try again.');
            if(error.response){
                console.log(error.response.data);
                console.log(error.response.status);
                console.log(error.response.headers);
            }else if(error.request){
                console.log(error.request);
            }else{
                console.log('Error', error.message);
            }
        } finally {
            setIsUploading(false);
        }
    };

    const handleChange = (event) =>{
        const nextFile = event.target.files[0] ?? null;
        if (!nextFile) {
            return;
        }

        setFile(nextFile);
        setUploadError('');
        setUploadProgres(0);

        if (uploadedFileURL) {
            uploadVideo(nextFile);
        }
    }

    const handleUploadAreaClick = () => {
        if (inputRef.current) {
            inputRef.current.value = '';
            inputRef.current.click();
        }
    };

    const handleDragOver = (event) => {
        event.preventDefault();
    };

    const handleDrop = (event) => {
        event.preventDefault();
        const droppedFile = event.dataTransfer.files?.[0] ?? null;
        if (!droppedFile) {
            return;
        }
        setFile(droppedFile);
        setUploadError('');
        setUploadProgres(0);
    };

    //async function handleSubmit(event){
    const handleSubmit = async (event) => {

        event.preventDefault();

        if (!file) {
            setUploadError('Select a video file before uploading.');
            return;
        }

        await uploadVideo(file);
    }

    //https://medium.com/@codeawake/ai-chatbot-frontend-1823b9c78521
    //https://github.com/ruizguille/tech-trends-chatbot

    //http://github.com/videojs/video.js/issues/5307
    //mp4 created with hevc is not supported by chrome only safary 

    const videoJsOptions = {
        //https://legacy.videojs.org/guides/options/
        autoplay: false,
        poster: true,
        loop: true,
        controls: true,
        responsive: true,
        fluid: true,  //true to take the parent div width and height
        backgroundColor: "black",
        display: "block",
        response: true,  //for the breakpoints
        forward:5,
        sources: [
        {
            src: uploadedFileURL,
            type: 'video/mp4',
        },
        ],
    };

    const handlePlayerReady = (player) => {
        playerRef.current = player;

        player.on('waiting', () => {
        console.log('Player is waiting');
        });

        player.on('dispose', () => {
        console.log('Player will dispose');
        });
    };

    return(
        <section className="upload-shell">
            <div className="upload-hero">
                <p className="upload-eyebrow">Video Research Workspace</p>
                <h1>Ask questions <span className="feature-heading-accent">about your videos</span></h1>
                <p className="upload-subtitle">Upload a clip, extract the audio pipeline, and move straight into the AI-assisted review flow.</p>
            </div>

            <div className={`upload-grid${uploadedFileURL ? ' upload-grid-loaded' : ''}`}>
                <div className="upload-center-card">
                    {!uploadedFileURL ? (
                        <form className="upload-dropzone" onSubmit={handleSubmit}>
                            <input
                                ref={inputRef}
                                className="upload-input"
                                type="file"
                                accept="video/*"
                                onChange={handleChange}
                            />

                            <button
                                type="button"
                                className="upload-dropzone-button"
                                onClick={handleUploadAreaClick}
                                onDragOver={handleDragOver}
                                onDrop={handleDrop}
                            >
                                <span className="upload-dropzone-icon">
                                    <CloudUpload size={48} strokeWidth={1.7} />
                                </span>
                                <span className="upload-dropzone-title">Drag and drop or click to upload</span>
                                <span className="upload-dropzone-copy">Supports video files and sends them directly to the backend processing pipeline.</span>
                            </button>

                            <div className="upload-form-footer">
                                <div className="upload-file-meta">
                                    <span className="upload-file-label">Selected file</span>
                                    <strong>{file ? file.name : 'No file selected yet'}</strong>
                                </div>
                                <button className="upload-submit" type="submit" disabled={!file || isUploading}>
                                    {isUploading ? <LoaderCircle className="spin" size={18} /> : <ChevronRight size={18} />}
                                    <span>{isUploading ? 'Uploading...' : 'Start analysis'}</span>
                                </button>
                            </div>

                            <div className="upload-progress-block">
                                <div className="upload-progress-labels">
                                    <span>Upload progress</span>
                                    <span>{uploadProgress}%</span>
                                </div>
                                <progress value={uploadProgress} max="100"></progress>
                            </div>

                            {uploadError ? <p className="upload-error">{uploadError}</p> : null}
                        </form>
                    ) : (
                        <div className="upload-loaded-stage">
                            <div className="upload-loaded-header">
                                <div>
                                    <p className="upload-status"><CheckCircle2 size={16} /> Video ready</p>
                                    <h2>{file?.name ?? 'Uploaded video'}</h2>
                                </div>
                                <button className="upload-secondary-action" type="button" onClick={handleUploadAreaClick}>
                                    Replace file
                                </button>
                                <input
                                    ref={inputRef}
                                    className="upload-input"
                                    type="file"
                                    accept="video/*"
                                    onChange={handleChange}
                                />
                            </div>
                            <div className='video-container'>
                                <VideoJSPlayer options={videoJsOptions} onReady={handlePlayerReady}/>
                            </div>
                        </div>
                    )}
                </div>

                {uploadedFileURL ? (
                    <div className="upload-chat-shell upload-chat-shell-inline">
                        <div className='chat-panel'>
                            <ChatBot/>
                        </div>
                    </div>
                ) : null}
            </div>

            {!uploadedFileURL ? (
                <div className="upload-lower-panel">
                    <div className="upload-chat-shell">
                        <div className="upload-chat-placeholder">
                            <MessageCircle size={20} strokeWidth={2} />
                            <input type="text" value="Upload a video to unlock the chat panel" readOnly />
                            <button type="button" disabled>
                                <ChevronRight size={18} strokeWidth={2} />
                            </button>
                        </div>
                    </div>
                </div>
            ) : null}
        </section>

    );

}

export default Proxeiro;