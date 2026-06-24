import useAutosize from '../hooks/useAutosize';
//import sendIcon from '../icons/logo.png';
import { Send } from 'lucide-react';
import '../styles/chatinput.css';

function ChatInput({ newMessage, isLoading, setNewMessage, submitNewMessage }) {
  const textareaRef = useAutosize(newMessage);

  function handleKeyDown(e) {
    if (e.keyCode === 13 && !e.shiftKey && !isLoading) {
      e.preventDefault();
      submitNewMessage();
    }
  }

  return (
    <div className="chat-input-wrapper">
      <div className="chat-input-outer">
        <div className="chat-input-inner">
          <textarea
            className="chat-textarea"
            ref={textareaRef}
            rows="1"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
          />
          <button
            className="chat-send-button"
            onClick={submitNewMessage}
          >
            <Send/>
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatInput;