import Markdown from 'react-markdown';
import useAutoScroll from '../hooks/useAutoScroll';
//import userIcon from '../icons/logo.png';
import { User, Bot, Loader2 } from 'lucide-react';
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
      {messages.map(({ role, content, loading, error, timestamps }, idx) => {
        if (loading && !content) {
          return (
            <div key={idx} className="chat-message chat-message-thinking">
              <div className="chat-message-avatar chat-message-avatar-assistant">
                <Bot size={14} />
              </div>
              <div className="chat-message-thinking-bubble">
                <Loader2 className="chat-message-thinking-spinner" size={14} />
                <span>Thinking…</span>
              </div>
            </div>
          );
        }

        return (
          <div
            key={idx}
            className={`chat-message ${role === 'user' ? 'chat-message-user' : ''}`}
          >
            <div className={`chat-message-avatar ${role === 'user' ? 'chat-message-avatar-user' : 'chat-message-avatar-assistant'}`}>
              {role === 'user' ? <User size={14} /> : <Bot size={14} />}
            </div>

            <div className="chat-message-content">
              <div className="markdown-container">
                {role === 'assistant' ? (
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
        );
      })}
    </div>
  );
}

export default ChatMessages;