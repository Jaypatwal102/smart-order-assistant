'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import styles from './page.module.css';

interface Message {
  id: string;
  sender_type: 'user' | 'human_agent' | 'bot';
  message_text: string;
}

export default function AgentDashboard() {
  const [queueSize, setQueueSize] = useState(0);
  const [currentConversation, setCurrentConversation] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  
  const [isChatEnded, setIsChatEnded] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
  const router = useRouter();

  useEffect(() => {
    // Check auth and role
    const checkAuth = async () => {
      const tokenMatch = document.cookie.match(/(^|;)\s*token\s*=\s*([^;]+)/);
      const token = tokenMatch ? tokenMatch[2] : null;
      if (!token) {
        router.push('/login');
        return;
      }
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (response.ok) {
          const userData = await response.json();
          if (userData.role !== 'HUMAN_AGENT') {
            router.push('/support');
            return;
          }
          connectWebSocket(userData.uid);
        } else {
          router.push('/login');
        }
      } catch (e) {
        router.push('/login');
      }
    };
    checkAuth();

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (peerConnectionRef.current) peerConnectionRef.current.close();
    };
  }, [router]);

  const connectWebSocket = (agentId: string) => {
    const wsUrl = `ws://localhost:8000/handoff/ws/agent/${agentId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'queue_update') {
        setQueueSize(data.queue_size);
      } else if (data.type === 'assigned') {
        setCurrentConversation(data.conversation_id);
        setIsConnected(true);
        setIsChatEnded(false);
        setupWebRTC(data.conversation_id);
        
        // Fetch history
        const tokenMatch = document.cookie.match(/(^|;)\s*token\s*=\s*([^;]+)/);
        const token = tokenMatch ? tokenMatch[2] : null;
        if (token) {
          try {
            fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/conversations/${data.conversation_id}`, {
              headers: { Authorization: `Bearer ${token}` }
            }).then(res => res.json()).then(conv => {
              if (conv.messages) {
                setMessages(conv.messages.map((m: any) => ({
                  id: m.mid,
                  sender_type: m.sender_type,
                  message_text: m.message_text
                })));
              }
            });
          } catch (e) {
            console.error(e);
          }
        }
      } else if (data.type === 'offer') {
        await handleOffer(data.payload, data.conversation_id);
      } else if (data.type === 'answer') {
        if (peerConnectionRef.current) {
          await peerConnectionRef.current.setRemoteDescription(new RTCSessionDescription(data.payload));
        }
      } else if (data.type === 'ice-candidate') {
        if (peerConnectionRef.current) {
          await peerConnectionRef.current.addIceCandidate(new RTCIceCandidate(data.payload));
        }
      } else if (data.type === 'chat_message') {
        if (!dataChannelRef.current || dataChannelRef.current.readyState !== 'open') {
          setMessages(prev => [...prev, {
            id: Math.random().toString(),
            sender_type: 'user',
            message_text: data.message
          }]);
        }
      }
    };
  };

  const setupWebRTC = async (conversationId: string) => {
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });
    peerConnectionRef.current = pc;

    pc.onicecandidate = (event) => {
      if (event.candidate && wsRef.current) {
        wsRef.current.send(JSON.stringify({
          type: 'ice-candidate',
          payload: event.candidate,
          conversation_id: conversationId
        }));
      }
    };

    // Agent creates the data channel
    const channel = pc.createDataChannel('chat');
    dataChannelRef.current = channel;
    
    channel.onmessage = (e) => {
      setMessages(prev => [...prev, {
        id: Math.random().toString(),
        sender_type: 'user',
        message_text: e.data
      }]);
    };
    
    channel.onopen = () => console.log("Data channel opened from agent");
    channel.onclose = () => {
      setIsConnected(false);
      setIsChatEnded(true);
      setMessages(prev => [...prev, {
        id: Math.random().toString(),
        sender_type: 'bot',
        message_text: 'The user has disconnected.'
      }]);
    };

    // Agent creates the offer
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({
        type: 'offer',
        payload: offer,
        conversation_id: conversationId
      }));
    }
  };

  const handleOffer = async (offer: RTCSessionDescriptionInit, conversationId: string) => {
    const pc = peerConnectionRef.current;
    if (!pc) return;

    await pc.setRemoteDescription(new RTCSessionDescription(offer));
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);

    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({
        type: 'answer',
        payload: answer,
        conversation_id: conversationId
      }));
    }
  };

  const acceptNext = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'accept_next' }));
      setMessages([]); // clear previous messages
    }
  };

  const endChat = () => {
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
      dataChannelRef.current = null;
    }
    setIsConnected(false);
    setIsChatEnded(true);
    setMessages(prev => [...prev, {
      id: Math.random().toString(),
      sender_type: 'bot',
      message_text: 'You have ended the chat.'
    }]);
  };

  const sendMessage = () => {
    if (!inputText.trim() || !currentConversation || isChatEnded) return;

    const msgText = inputText;
    setInputText('');

    // Update local state
    setMessages(prev => [...prev, {
      id: Math.random().toString(),
      sender_type: 'human_agent',
      message_text: msgText
    }]);

    // Send via Data Channel if open, otherwise fallback to WS
    if (dataChannelRef.current && dataChannelRef.current.readyState === 'open') {
      dataChannelRef.current.send(msgText);
      // Sync to DB via WS
      wsRef.current?.send(JSON.stringify({
        type: 'chat_message',
        conversation_id: currentConversation,
        message: msgText
      }));
    } else {
      // Fallback via WS directly if DataChannel isn't ready
      wsRef.current?.send(JSON.stringify({
        type: 'chat_message',
        conversation_id: currentConversation,
        message: msgText
      }));
    }
  };

  return (
    <div className={`${styles.container} ${isDarkMode ? styles.darkMode : ''}`}>
      {/* Sidebar */}
      <div className={styles.sidebar}>
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}>SOA Agent</h1>
            <p className={styles.subtitle}>Human Support Dashboard</p>
          </div>
          <div className={styles.headerActions}>
            <button onClick={() => setIsDarkMode(!isDarkMode)} aria-label="Toggle Theme">
              {isDarkMode ? (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
              )}
            </button>
          </div>
        </div>

        <div className={styles.stats}>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Users in Queue</span>
            <span className={styles.statValue}>{queueSize}</span>
          </div>
        </div>

        <button 
          className={styles.actionBtn} 
          onClick={acceptNext} 
          disabled={queueSize === 0 || (isConnected && !isChatEnded)}
        >
          {isConnected && !isChatEnded ? 'In Conversation' : 'Accept Next User'}
        </button>
      </div>

      {/* Main Chat Area */}
      <div className={styles.mainContent}>
        {currentConversation ? (
          <>
            <div className={styles.chatHeader}>
              <h2 className={styles.chatTitle}>Conversation</h2>
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                <div className={`${styles.statusBadge} ${isConnected ? '' : styles.disconnected}`}>
                  {isConnected ? 'Connected via WebRTC' : (isChatEnded ? 'Chat Ended' : 'Connecting...')}
                </div>
                {!isChatEnded && (
                  <button onClick={endChat} style={{ 
                    padding: '6px 12px', 
                    borderRadius: '6px', 
                    border: '1px solid #ef4444', 
                    color: '#ef4444', 
                    background: 'transparent',
                    cursor: 'pointer'
                  }}>
                    End Chat
                  </button>
                )}
              </div>
            </div>
            
            <div className={styles.chatArea}>
              {messages.map(m => (
                <div key={m.id} className={`${styles.message} ${m.sender_type === 'human_agent' ? styles.messageAgent : styles.messageUser}`} style={m.sender_type === 'bot' ? { alignSelf: 'center', backgroundColor: 'transparent', color: '#94a3b8', border: 'none', fontStyle: 'italic', fontSize: '0.9rem' } : {}}>
                  {m.message_text}
                </div>
              ))}
            </div>

            <div className={styles.inputArea}>
              <input 
                type="text" 
                className={styles.input} 
                placeholder={isChatEnded ? "Chat has ended." : "Type your message..."}
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                onKeyDown={e => e.key === 'Enter' ? sendMessage() : null}
                disabled={isChatEnded}
              />
              <button className={styles.sendBtn} onClick={sendMessage} disabled={isChatEnded}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
              </button>
            </div>
          </>
        ) : (
          <div className={styles.emptyState}>
            <div className={styles.emptyStateIcon}>
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
            </div>
            <h2>Waiting for users</h2>
            <p>Accept a user from the queue to start chatting.</p>
          </div>
        )}
      </div>
    </div>
  );
}
