import { useState } from 'react';
import { useImmer } from 'use-immer';
// import api from '@/api';
// import { parseSSEStream } from '@/utils';
import { Bot } from 'lucide-react';
import ChatMessages from './ChatMessages';
import ChatInput from './ChatInput';
import '../styles/chatbot.css';

const QUICK_ACTIONS = [
  {
    label: 'Summarize this video',
    prompt: 'Summarize this video',
  },
];

function Chatbot({ onSeek, videoId }) {
  const [chatId, setChatId] = useState(null);
  const [messages, setMessages] = useImmer([]);
  const [newMessage, setNewMessage] = useState('');
  const [showQuickActions, setShowQuickActions] = useState(true);

  const isLoading =
    messages.length && messages[messages.length - 1].loading;

  async function submitNewMessage(overrideText) {
    const trimmedMessage = (overrideText ?? newMessage).trim();

    if (!trimmedMessage || isLoading) return;

    if (trimmedMessage.toLowerCase() === 'summarize this video') {
      setShowQuickActions(false);
    }

    // Add user message
    setMessages((draft) => {
      draft.push({
        role: "user",
        content: trimmedMessage,
      });

      draft.push({
        role: "assistant",
        content: "",
        loading: true,
      });
    });

    setNewMessage("");

    try {
      // Send recent prior turns so the backend/LLM can handle follow-up
      // questions ("what about that?") instead of treating every question
      // in isolation. Exclude loading/error placeholders -- only real
      // exchanged content is useful context.
      const history = messages
        .filter((m) => !m.loading && !m.error && m.content)
        .map((m) => ({ role: m.role, content: m.content }))
        .slice(-6);

      const response = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: trimmedMessage,
          video_id: videoId,
          history,
        }),
      });

      if (!response.ok) {
        throw new Error("Backend error");
      }

      const data = await response.json();
      const fullAnswer = data.answer ?? "";

      setMessages((draft) => {
        draft[draft.length - 1] = {
          role: "assistant",
          content: "",
          timestamps: data.timestamps ?? [],
          loading: false,
        };
      });

      if (fullAnswer) {
        const speed = Math.max(12, Math.min(40, 1200 / Math.max(fullAnswer.length, 1)));
        let index = 0;

        const intervalId = window.setInterval(() => {
          index += 1;

          setMessages((draft) => {
            if (draft[draft.length - 1]?.role === "assistant") {
              draft[draft.length - 1] = {
                ...draft[draft.length - 1],
                content: fullAnswer.slice(0, index),
              };
            }
          });

          if (index >= fullAnswer.length) {
            window.clearInterval(intervalId);
          }
        }, speed);
      } else {
        setMessages((draft) => {
          draft[draft.length - 1] = {
            role: "assistant",
            content: "",
            timestamps: data.timestamps ?? [],
            loading: false,
          };
        });
      }

    } catch (err) {
      console.error(err);

      setMessages((draft) => {
        draft[draft.length - 1] = {
          role: "assistant",
          content: "Something went wrong.",
          loading: false,
          error: true,
        };
      });
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className={`chatbot ${isEmpty ? 'chatbot-empty' : 'chatbot-live'}`}>

      <div className="chatbot-header">
        <div className="chatbot-header-icon">
          <Bot size={18} />
        </div>
        <div>
          <p className="chatbot-header-title">Video AI</p>
          <div className="chatbot-header-status">
            <span className="chatbot-header-dot" />
            <span>Ready to chat</span>
          </div>
        </div>
      </div>

      {!isEmpty && <ChatMessages messages={messages} isLoading={isLoading} onSeek={onSeek} />}

      {showQuickActions && (
        <div className="chatbot-quick-actions" aria-label="Quick actions">
          {QUICK_ACTIONS.map(({ label, prompt }) => (
            <button
              key={label}
              type="button"
              className="chatbot-quick-action"
              onClick={() => submitNewMessage(prompt)}
              disabled={isLoading}
            >
              <span>{label}</span>
            </button>
          ))}
        </div>
      )}

      {isEmpty && <div className="chatbot-empty-spacer" />}

      <ChatInput
        newMessage={newMessage}
        isLoading={isLoading}
        setNewMessage={setNewMessage}
        submitNewMessage={() => submitNewMessage()}
      />
    </div>
  );
}

export default Chatbot;