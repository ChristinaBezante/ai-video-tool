import useAutosize from '../hooks/useAutosize';
import { Send, Plus, Mic } from 'lucide-react';
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
          <button className="chat-aux-button chat-aux-left" type="button" aria-label="Add attachment">
            <Plus />
          </button>

          <textarea
            className="chat-textarea"
            ref={textareaRef}
            rows="1"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
          />
          <button className="chat-aux-button chat-aux-right" type="button" aria-label="Voice input">
            <Mic />
          </button>
          <button
            className="chat-send-button"
            onClick={submitNewMessage}
            aria-label="Send message"
          >
            <Send/>
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatInput;