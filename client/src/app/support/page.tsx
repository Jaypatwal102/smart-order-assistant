"use client";

import React, { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, Plus, Headphones, ChevronDown, 
  ShoppingBag, Sun, Mic, ArrowUp, Sparkles, Check, Edit2 
} from 'lucide-react';
import styles from './support.module.css';
import { getCurrentUser, logoutUser, sendMessage } from '@/utils/auth';
import { useRouter } from 'next/navigation';

interface Message {
  id: string;
  sender: 'ai' | 'user';
  text?: string;
  time: string;
  isCustomCard?: boolean;
}

export default function SupportPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const [allConversations, setAllConversations] = useState<any[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);

  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  useEffect(() => {
    async function loadUser() {
      try {
        const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
        if (!token) {
          router.push('/login');
          return;
        }

        const userData = await getCurrentUser(token);
        setUser(userData);
        if (userData.conversations && userData.conversations.length > 0) {
          setAllConversations(userData.conversations);
        }
      } catch (err) {
        console.error('Failed to load user', err);
        logoutUser();
        router.push('/login');
      } finally {
        setLoading(false);
      }
    }

    loadUser();
  }, [router]);

  useEffect(() => {
    if (user && messages.length === 0 && !activeConversationId) {
      setMessages([
        {
          id: '1',
          sender: 'ai',
          text: `Hello ${user.first_name || user.email.split('@')[0]}! 👋\nI'm your AI support assistant. How can I help you today?`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    }
  }, [user, messages.length, activeConversationId]);

  const loadConversation = (conv: any) => {
    setActiveConversationId(conv.id);
    if (!conv.messages || conv.messages.length === 0) {
      setMessages([
        {
          id: '1',
          sender: 'ai',
          text: `Hello ${user?.first_name || user?.email?.split('@')[0]}! 👋\nI'm your AI support assistant. How can I help you today?`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      return;
    }

    const formattedMsgs = conv.messages.map((m: any) => {
      let timeStr = '';
      if (m.created_at) {
        timeStr = new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      }
      return {
        id: m.id,
        sender: m.sender_type === 'bot' || m.sender_type === 'ai' ? 'ai' : 'user',
        text: m.message_text,
        time: timeStr
      };
    });
    setMessages(formattedMsgs);
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f172a' }}>
        <div style={{ width: '40px', height: '40px', border: '4px solid rgba(129, 140, 248, 0.2)', borderTopColor: '#818cf8', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userText = inputValue;
    const newUserMessage: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: userText,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, newUserMessage]);
    setInputValue('');
    setIsTyping(true);

    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
      if (!token) throw new Error("No token found");

      const updatedConv = await sendMessage(token, userText, activeConversationId);
      
      // Update the active conversation ID in case it was a new conversation
      setActiveConversationId(updatedConv.id);

      // Map messages back to UI format
      const formattedMsgs = updatedConv.messages.map((m: any) => ({
        id: m.id,
        sender: m.sender_type === 'bot' || m.sender_type === 'ai' ? 'ai' : 'user',
        text: m.message_text,
        time: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
      }));

      setMessages(formattedMsgs);

      // Update allConversations in Sidebar
      setAllConversations(prev => {
        const index = prev.findIndex(c => c.id === updatedConv.id);
        if (index >= 0) {
          const newAll = [...prev];
          newAll[index] = updatedConv;
          return newAll;
        } else {
          return [updatedConv, ...prev];
        }
      });
    } catch (err) {
      console.error("Failed to send message", err);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  };

  return (
    <div className={styles.container}>
      {/* Sidebar */}
      <div className={styles.sidebar}>
        <div className={styles.logo}>AMU</div>
        
        <button className={styles.newChatBtn} onClick={() => {
          setActiveConversationId(null);
          setMessages([
            {
              id: '1',
              sender: 'ai',
              text: `Hello ${user?.first_name || user?.email?.split('@')[0]}! 👋\nI'm your AI support assistant. How can I help you today?`,
              time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }
          ]);
        }}>
          <Plus size={18} /> New Chat
        </button>

        <div className={styles.historySection}>
          <div className={styles.historyGroup}>
            <div className={styles.historyTitle}>Your Conversations</div>
            {allConversations.length === 0 && (
              <div style={{ color: '#a09fa5', fontSize: '13px', padding: '10px 16px' }}>No previous conversations</div>
            )}
            {allConversations.map(conv => {
              // Try to find the first user message for title, otherwise generic
              const firstUserMsg = conv.messages?.find((m: any) => m.sender_type === 'user');
              const title = firstUserMsg ? firstUserMsg.message_text.substring(0, 30) + (firstUserMsg.message_text.length > 30 ? '...' : '') : 'New Conversation';
              
              let timeStr = '';
              if (conv.started_at) {
                const date = new Date(conv.started_at);
                timeStr = date.toLocaleDateString() === new Date().toLocaleDateString() 
                  ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : date.toLocaleDateString();
              }

              return (
                <div 
                  key={conv.id} 
                  className={styles.historyItem} 
                  style={{ background: activeConversationId === conv.id ? 'rgba(255,255,255,0.05)' : 'transparent' }}
                  onClick={() => loadConversation(conv)}
                >
                  <div className={styles.historyText}>
                    <MessageSquare size={16} color="#a09fa5" style={{ flexShrink: 0 }} /> 
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{title}</span>
                  </div>
                  <div className={styles.historyTime}>{timeStr}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className={styles.helpCard}>
          <div className={styles.helpHeader}>
            <div className={styles.helpIcon}>
              <Headphones size={18} />
            </div>
            <div>
              <div className={styles.helpTitle}>Need immediate help?</div>
            </div>
          </div>
          <div className={styles.helpSubtitle}>Talk to our human support</div>
          <button className={styles.contactBtn}>
            <Headphones size={16} /> Contact Support
          </button>
        </div>

        <div className={styles.userProfile}>
          <div className={styles.userAvatar}>F</div>
          <div className={styles.userInfo}>
            <div className={styles.userName}>Fletcher</div>
            <div className={styles.userEmail}>fletcher@example.com</div>
          </div>
          <ChevronDown size={16} color="#a09fa5" cursor="pointer" />
        </div>
      </div>

      {/* Main Area */}
      <div className={styles.mainArea}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerTitle}>
            <Sparkles size={20} color="#7c5dfa" /> AI Support Assistant
          </div>
          <div className={styles.headerActions}>
            <button className={styles.viewOrdersBtn}>
              <ShoppingBag size={16} /> View Orders
            </button>
            <button className={styles.iconBtn}>
              <Sun size={18} />
            </button>
          </div>
        </div>

        {/* Chat Container */}
        <div className={styles.chatContainer}>
          {messages.map((msg) => (
            <div key={msg.id} className={`${styles.messageRow} ${msg.sender === 'ai' ? styles.ai : styles.user}`}>
              {msg.sender === 'ai' && (
                <div className={styles.aiAvatar}>
                  <Sparkles size={20} color="#fff" />
                </div>
              )}
              
              <div className={styles.messageContent}>
                {msg.isCustomCard ? (
                  <div className={styles.messageBubble}>
                    <div className={styles.orderCard}>
                      <div className={styles.orderCardTitle}>Current shipping address</div>
                      <div className={styles.orderCardDetails}>
                        123 Maple Street<br />
                        San Francisco, CA 94107<br />
                        United States
                      </div>
                      <button className={styles.orderCardAction}>
                        <Edit2 size={14} /> Update address
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className={styles.messageBubble}>
                    {msg.text?.split('\n').map((line, i) => (
                      <React.Fragment key={i}>
                        {line}
                        {i !== msg.text!.split('\n').length - 1 && <br />}
                      </React.Fragment>
                    ))}
                  </div>
                )}
                <div className={styles.messageTime}>
                  {msg.time}
                  {msg.sender === 'user' && <Check size={14} color="#a09fa5" style={{ marginLeft: 4 }} />}
                </div>
              </div>
            </div>
          ))}

          {isTyping && (
            <div className={`${styles.messageRow} ${styles.ai}`}>
              <div className={styles.aiAvatar}>
                <Sparkles size={20} color="#fff" />
              </div>
              <div className={styles.messageContent}>
                <div className={styles.messageBubble}>
                  <div className={styles.typingIndicator}>
                    <div className={styles.typingDot}></div>
                    <div className={styles.typingDot}></div>
                    <div className={styles.typingDot}></div>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className={styles.inputArea}>
          <div className={styles.inputContainer}>
            <input
              type="text"
              className={styles.chatInput}
              placeholder="Type your message..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <div className={styles.inputActions}>
              <button className={styles.audioBtn}>
                <Mic size={20} />
              </button>
              <button className={styles.sendBtn} onClick={handleSendMessage}>
                <ArrowUp size={20} />
              </button>
            </div>
          </div>
          <div className={styles.inputHint}>
            <Sparkles size={12} /> You can also speak to send a message
          </div>
        </div>
      </div>
    </div>
  );
}
