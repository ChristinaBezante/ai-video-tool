import '../styles/proxeiro.css'
import React,{useEffect, useRef, useState} from 'react';
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
    const [backendProgress, setBackendProgress] = useState(0);
    const [uploadedFileURL, setUploadedFileURL] = useState(null);
    const [uploadError, setUploadError] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const [processingStage, setProcessingStage] = useState('idle');

    const playerRef = React.useRef(null);
    const uploadInputRef = useRef(null);
    const replaceInputRef = useRef(null);

    useEffect(() => {
        return () => {
            setIsUploading(false);
        };
    }, []);

    const stageLabel = (stage) => {
        if (stage === 'extracting_audio') return 'Processing: extracting audio...';
        //if (stage === 'transcribing') return 'Processing: transcribing audio...';
        //if (stage === 'extracting_frames') return 'Processing: extracting frames...';
        if (stage === 'queued') return 'Processing queued...';
        if (stage === 'completed') return 'Processing completed.';
        if (stage === 'failed') return 'Processing failed.';
        return '';
    };

    const wait = (ms) => new Promise((resolve) => {
        setTimeout(resolve, ms);
    });

    const pollUploadStatus = async (jobId) => {
        const statusUrl = `http://localhost:8000/upload-status/${jobId}`;

        for (let attempt = 0; attempt < 600; attempt += 1) {
            const { data } = await axios.get(statusUrl);
            const status = data?.status;
            const stage = data?.stage || 'processing';
            const progress = Number(data?.progress ?? 0);
            setProcessingStage(stage);
            if (!Number.isNaN(progress)) {
                setBackendProgress(Math.max(0, Math.min(100, progress)));
            }

            if (status === 'completed') {
                const result = data?.result || {};
                const fileUrl = `http://localhost:8000${result.file_url}?t=${Date.now()}`;
                setUploadedFileURL(fileUrl);
                return;
            }

            if (status === 'failed') {
                throw new Error(data?.error || 'Upload processing failed.');
            }

            await wait(1200);
        }

        throw new Error('Processing timed out. Try a shorter video or retry.');
    };

    const uploadVideo = async (fileToUpload) => {
        const url = 'http://localhost:8000/uploadfile/';
        const formData = new FormData();
        formData.append('file_upload', fileToUpload);
        formData.append('filename', fileToUpload.name);

        try{
            setIsUploading(true);
            setUploadError('');
            setUploadedFileURL(null);
            setProcessingStage('uploading');
            setBackendProgress(0);
            const config = {
                onUploadProgress: progressEvent => {
                    const total = progressEvent.total || 1;
                    const percentCompleted = Math.round((progressEvent.loaded * 100) / total);
                    setUploadProgres(percentCompleted);
                }
            }
            const response = await axios.post(url, formData, config);
            setUploadProgres(100);
            const jobId = response?.data?.job_id;

            if (jobId) {
                setProcessingStage('queued');
                await pollUploadStatus(jobId);
                setBackendProgress(100);
                setProcessingStage('completed');
            } else if (response?.data?.file_url) {
                // Backward-compatible path for synchronous backend responses.
                const fileUrl = `http://localhost:8000${response.data.file_url}?t=${Date.now()}`;
                setUploadedFileURL(fileUrl);
                setBackendProgress(100);
                setProcessingStage('completed');
            } else {
                throw new Error('Unexpected backend response. Missing job_id or file_url.');
            }
        }catch(error){
            setUploadError(error?.message || 'Upload failed. Check that the FastAPI backend is running and try again.');
            setProcessingStage('failed');
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
        setBackendProgress(0);

        if (uploadedFileURL) {
            uploadVideo(nextFile);
        }
    }

    const handleUploadAreaClick = () => {
        if (uploadInputRef.current) {
            uploadInputRef.current.value = '';
            uploadInputRef.current.click();
        }
    };

    const handleReplaceClick = () => {
        if (replaceInputRef.current) {
            replaceInputRef.current.value = '';
            replaceInputRef.current.click();
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
        setBackendProgress(0);
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
        fill: true,   // fill parent container dimensions
        backgroundColor: "black",
        display: "block",
        forward:5,
        sources: [
        {
            src: uploadedFileURL,
            type: 'video/mp4',
        },
        ],
    };

    const displayProgress = processingStage === 'uploading' ? uploadProgress : backendProgress;

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
                {/*<p className="upload-eyebrow">Video Research Workspace</p>*/}
                <h1>Ask questions <span className="feature-heading-accent">about your videos</span></h1>
                <p className="upload-subtitle">Upload a clip, extract the audio pipeline, and move straight into the AI-assisted review flow.</p>
            </div>

            <div className={`upload-grid${uploadedFileURL ? ' upload-grid-loaded' : ''}`}>
                <div className="upload-center-card">
                    {!uploadedFileURL ? (
                        <form className="upload-dropzone" onSubmit={handleSubmit}>
                            <input
                                ref={uploadInputRef}
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
                                    <span>{isUploading ? 'Working...' : 'Start analysis'}</span>
                                </button>
                            </div>

                            <div className="upload-progress-block">
                                <div className="upload-progress-labels">
                                    <span>{processingStage === 'uploading' ? 'Upload progress' : 'Backend progress'}</span>
                                    <span>{displayProgress}%</span>
                                </div>
                                <progress value={displayProgress} max="100"></progress>
                                {isUploading && processingStage !== 'uploading' ? (
                                    <p className="upload-file-label">{stageLabel(processingStage)}</p>
                                ) : null}
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
                                <button className="upload-secondary-action" type="button" onClick={handleReplaceClick}>
                                    Replace file
                                </button>
                                <input
                                    ref={replaceInputRef}
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