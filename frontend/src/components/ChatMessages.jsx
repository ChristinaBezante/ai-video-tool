import Markdown from 'react-markdown';
import useAutoScroll from '../hooks/useAutoScroll';
import Spinner from './Spinner';
//import userIcon from '../icons/logo.png';
import { User } from 'lucide-react';
//import errorIcon from '../icons/logo.png';
import { CircleX } from 'lucide-react';
import '../styles/chatmessages.css';

function ChatMessages({ messages, isLoading }) {
  const scrollContentRef = useAutoScroll(isLoading);

  return (
    <div ref={scrollContentRef} className="chat-messages">
      {messages.map(({ role, content, loading, error }, idx) => (
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