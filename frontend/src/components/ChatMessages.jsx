import Markdown from 'react-markdown';
import useAutoScroll from '../hooks/useAutoScroll';
import Spinner from './Spinner';
//import userIcon from '../icons/logo.png';
import { User } from 'lucide-react';
//import errorIcon from '../icons/logo.png';
import { CircleX } from 'lucide-react';
import '../styles/chatmessages.css';

function formatTimestamp(seconds) {
  if (seconds == null || isNaN(seconds)) return null;
  const s = Math.floor(seconds);
  const m = Math.floor(s / 60);
  const ss = String(s % 60).padStart(2, '0');
  return `${m}:${ss}`;
}

function ChatMessages({ messages, isLoading, onSeek }) {
  const scrollContentRef = useAutoScroll(isLoading);

  return (
    <div ref={scrollContentRef} className="chat-messages">
      {messages.map(({ role, content, loading, error, timestamps }, idx) => (
        <div
          key={idx}
          className={`chat-message ${role === 'user' ? 'chat-message-user' : ''}`}
        >
          {role === 'user' && (
              <User className="chat-message-user-icon"/>
          )}

          <div className="chat-message-content">
            <div className="markdown-container">
              {loading && !content ? (
                <Spinner />
              ) : role === 'assistant' ? (
                <Markdown>{content}</Markdown>
              ) : (
                <div className="chat-message-text">{content}</div>
              )}
            </div>

            {role === 'assistant' && !loading && timestamps && timestamps.length > 0 && (
              <div className="chat-message-timestamp">
                {timestamps.map((ts, i) => (
                  <button
                    key={i}
                    type="button"
                    className="chat-message-timestamp-badge"
                    onClick={() => onSeek && onSeek(ts.start)}
                  >
                    ⏱ {formatTimestamp(ts.start)}
                  </button>
                ))}
              </div>
            )}

            {error && (
              <div
                className={`chat-message-error ${content ? 'chat-message-error-with-margin' : ''}`}
              >
                <CircleX className="chat-message-error-icon"/>
                <span>Error generating the response</span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export default ChatMessages;