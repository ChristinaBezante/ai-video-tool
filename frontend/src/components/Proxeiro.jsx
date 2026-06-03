//https://blog.filestack.com/react-file-upload-tutorial-filestack/

import '../styles/proxeiro.css'
import React,{useState} from 'react';
import axios from 'axios';  ///do in terminal npm install axios
//pip install "fastapi[standard]"
//to run fastapi dev main.py
//npm i video.js
import VideoJSPlayer from './VideoJSPlayer';

const Proxeiro = () => {

    const [file, setFile] = useState();
    const [uploadProgress, setUploadProgres] = useState(0);
    const [uploadedFileURL, setUploadedFileURL] = useState(null);

    const playerRef = React.useRef(null);

    const handleChange = (event) =>{
        setFile(event.target.files[0]);
    }

    //async function handleSubmit(event){
    const handleSubmit = async (event) => {

        event.preventDefault();

        const url = 'http://localhost:8000/uploadfile/'; 
        const formData = new FormData();
        formData.append('file_upload', file);
        formData.append('filename', file.name);
        // const config={
        //     headers:{
        //         'content-type': 'multipart/form-data',
        //     },
        // };
        try{
            //axios.post(url,formData,config).then((response) => {
            //console.log(response.data)});
            // const response = await axios.post(url, formData, {
            //     headers: {
            //         'Content-Type': 'multipart/form-data',
            //     },
            //  });
            const config = {
                //https://stackoverflow.com/questions/41088022/how-to-get-onuploadprogress-in-axios
                onUploadProgress: progressEvent => {
                    const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                    setUploadProgres(percentCompleted);
                }
            }
            const response = await axios.post(url, formData, config);
            setUploadedFileURL(`http://localhost:8000${response.data.file_url}`);
            console.log(response.data);  
            console.log(response.data.file_url);          
        }catch(error){
            if(error.response){
                console.log(error.response.data);
                console.log(error.response.status);
                console.log(error.response.headers);
            }else if(error.request){
                console.log(error.request);
            }else{
                console.log('Error', error.message);
            }
        }
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
        <>
            {!uploadedFileURL? (
                <div className="uploader-container"> 
                    <form action="" onSubmit={handleSubmit}>
                        <h1>React FileUploader</h1>
                        <input type="file" name="" id="" onChange={handleChange} />
                        <button type="submit">Upload</button>
                        <progress value={uploadProgress} max="100"></progress>
                    </form>
                    {/*uploadedFileURL && <img src={uploadedFileURL} alt="Uploaded file" />*/}
                    {/*https://www.w3schools.com/Html/html5_video.asp*/}
                    {/*uploadedFileURL && <video  width="320" height="240" controls><source src={uploadedFileURL} type="video/mp4" /></video>*/}
                    {/*uploadedFileURL && <VideoJSPlayer options={videoJsOptions} onReady={handlePlayerReady}/>*/}
                </div>
            ) : (
                <div className='videochat-container'>
                    <div className='video-container'>
                        
                        <VideoJSPlayer options={videoJsOptions} onReady={handlePlayerReady}/>
                    </div>
                    <div className='chat-container'>
                        <div className='chat'>

                        </div>
                    </div>
                </div>
            )}
        </>

    );

}

export default Proxeiro;