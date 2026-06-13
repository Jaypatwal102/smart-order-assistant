"use client";

import React, { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, Plus, Headphones, ChevronDown, 
  ShoppingBag, Sun, Mic, ArrowUp, Sparkles, Check, Edit2 
} from 'lucide-react';
import styles from './support.module.css';
import { getCurrentUser, logoutUser } from '@/utils/auth';
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

  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      sender: 'ai',
      text: 'Hello Fletcher! 👋\nI\'m your AI support assistant. How can I help you today?',
      time: '10:24 AM'
    },
    {
      id: '2',
      sender: 'user',
      text: 'I want to update my shipping address for order #AMU12345',
      time: '10:25 AM'
    },
    {
      id: '3',
      sender: 'ai',
      text: 'Sure! I can help you with that.\nPlease confirm your new shipping address.',
      time: '10:25 AM'
    },
    {
      id: '4',
      sender: 'ai',
      isCustomCard: true,
      time: '10:25 AM'
    },
    {
      id: '5',
      sender: 'user',
      text: 'Yes, I want to change it.',
      time: '10:26 AM'
    }
  ]);
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
    if (user) {
      setMessages(prev => {
        const newMsgs = [...prev];
        if (newMsgs[0] && newMsgs[0].id === '1') {
          newMsgs[0] = {
            ...newMsgs[0],
            text: `Hello ${user.first_name || user.email.split('@')[0]}! 👋\nI'm your AI support assistant. How can I help you today?`
          };
        }
        return newMsgs;
      });
    }
  }, [user]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f172a' }}>
        <div style={{ width: '40px', height: '40px', border: '4px solid rgba(129, 140, 248, 0.2)', borderTopColor: '#818cf8', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  const handleSendMessage = () => {
    if (!inputValue.trim()) return;

    const newUserMessage: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: inputValue,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, newUserMessage]);
    setInputValue('');
    setIsTyping(true);

    // Simulate AI response
    setTimeout(() => {
      setIsTyping(false);
      const newAiMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: 'I have updated your request. A support agent will verify the changes shortly. Is there anything else I can help with?',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, newAiMessage]);
    }, 1500);
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
        
        <button className={styles.newChatBtn}>
          <Plus size={18} /> New Chat
        </button>

        <div className={styles.historySection}>
          <div className={styles.historyGroup}>
            <div className={styles.historyTitle}>Today</div>
            <div className={styles.historyItem}>
              <div className={styles.historyText}>
                <MessageSquare size={16} color="#a09fa5" /> Update shipping address
              </div>
              <div className={styles.historyTime}>10:24 AM</div>
            </div>
            <div className={styles.historyItem}>
              <div className={styles.historyText}>
                <MessageSquare size={16} color="#a09fa5" /> Track my order
              </div>
              <div className={styles.historyTime}>09:15 AM</div>
            </div>
            <div className={styles.historyItem}>
              <div className={styles.historyText}>
                <MessageSquare size={16} color="#a09fa5" /> Return an item
              </div>
              <div className={styles.historyTime}>Yesterday</div>
            </div>
            <div className={styles.historyItem}>
              <div className={styles.historyText}>
                <MessageSquare size={16} color="#a09fa5" /> Order not delivered
              </div>
              <div className={styles.historyTime}>Yesterday</div>
            </div>
          </div>

          <div className={styles.historyGroup}>
            <div className={styles.historyTitle}>Previous 7 days</div>
            <div className={styles.historyItem}>
              <div className={styles.historyText}>
                <MessageSquare size={16} color="#a09fa5" /> Change payment method
              </div>
              <div className={styles.historyTime}>3 days ago</div>
            </div>
            <div className={styles.historyItem}>
              <div className={styles.historyText}>
                <MessageSquare size={16} color="#a09fa5" /> Cancel order
              </div>
              <div className={styles.historyTime}>4 days ago</div>
            </div>
            <div className={styles.historyItem}>
              <div className={styles.historyText}>
                <MessageSquare size={16} color="#a09fa5" /> Product support
              </div>
              <div className={styles.historyTime}>5 days ago</div>
            </div>
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
          <div className={styles.userAvatar}>
            {user?.first_name ? user.first_name[0].toUpperCase() : user?.email?.[0].toUpperCase() || 'U'}
          </div>
          <div className={styles.userInfo}>
            <div className={styles.userName}>{user?.first_name ? `${user.first_name} ${user.last_name || ''}` : 'User'}</div>
            <div className={styles.userEmail}>{user?.email || ''}</div>
          </div>
          <ChevronDown size={16} color="#a09fa5" cursor="pointer" onClick={() => {
            logoutUser();
            router.push('/login');
          }} />
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
