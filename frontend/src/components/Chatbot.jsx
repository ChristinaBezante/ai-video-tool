import { useState } from 'react';
import { useImmer } from 'use-immer';
// import api from '@/api';
// import { parseSSEStream } from '@/utils';
import { Bot } from 'lucide-react';
import ChatMessages from './ChatMessages';
import ChatInput from './ChatInput';
import '../styles/chatbot.css';

function Chatbot({ onSeek }) {
  const [chatId, setChatId] = useState(null);
  const [messages, setMessages] = useImmer([]);
  const [newMessage, setNewMessage] = useState('');

  const isLoading =
    messages.length && messages[messages.length - 1].loading;

  async function submitNewMessage(overrideText) {
    const trimmedMessage = (overrideText ?? newMessage).trim();

    if (!trimmedMessage || isLoading) return;

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
      const response = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: trimmedMessage,
        }),
      });

      if (!response.ok) {
        throw new Error("Backend error");
      }

      const data = await response.json();

      setMessages((draft) => {
        draft[draft.length - 1] = {
          role: "assistant",
          content: data.answer,
          timestamps: data.timestamps ?? [],
          loading: false,
        };
      });

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