"use client";

import React, { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, Plus, Headphones, ChevronDown, 
  ShoppingBag, Sun, Moon, Mic, ArrowUp, Sparkles, Check, Edit2 
} from 'lucide-react';
import styles from './support.module.css';
import { getCurrentUser, logoutUser, sendMessage, sendAudioMessage } from '@/utils/auth';
import { useRouter } from 'next/navigation';

interface Message {
  id: string;
  sender: 'ai' | 'user' | 'human_agent';
  text?: string;
  time: string;
  isCustomCard?: boolean;
}

export default function SupportPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isLightMode, setIsLightMode] = useState(false);

  const [allConversations, setAllConversations] = useState<any[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);

  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  
  // Handoff state
  const [isHandedOver, setIsHandedOver] = useState(false);
  const [isConnectedToAgent, setIsConnectedToAgent] = useState(false);
  const [agentId, setAgentId] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<BlobPart[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (peerConnectionRef.current) peerConnectionRef.current.close();
    };
  }, []);

  useEffect(() => {
    async function loadUser() {
      try {
        const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
        if (!token) {
          router.push('/login');
          return;
        }

        const userData = await getCurrentUser(token);
        if (userData.role === 'HUMAN_AGENT') {
          router.push('/agent');
          return;
        }
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

  const loadConversation = async (conv: any) => {
    setActiveConversationId(conv.cid);
    if (conv.status?.toLowerCase() === 'handed_over') {
      setIsHandedOver(true);
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connectWebSocket(conv.cid);
      }
    } else {
      setIsHandedOver(false);
      setIsConnectedToAgent(false);
      setAgentId(null);
      if (wsRef.current) wsRef.current.close();
      if (peerConnectionRef.current) peerConnectionRef.current.close();
    }

    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
      if (!token) return;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/conversations/${conv.cid}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) return;
      const fullConv = await res.json();

      if (!fullConv.messages || fullConv.messages.length === 0) {
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

      const formattedMsgs = fullConv.messages.map((m: any) => {
        let timeStr = '';
        if (m.created_at) {
          timeStr = new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        return {
          id: m.mid,
          sender: m.sender_type?.toUpperCase() === 'BOT' || m.sender_type?.toUpperCase() === 'AI' ? 'ai' : (m.sender_type?.toUpperCase() === 'HUMAN_AGENT' ? 'human_agent' : 'user'),
          text: m.message_text,
          time: timeStr
        };
      });
      setMessages(formattedMsgs);
      
      if (fullConv.status === 'HANDED_OVER' || fullConv.status === 'handed_over') {
        setIsHandedOver(true);
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          connectWebSocket(fullConv.cid);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const connectWebSocket = (conversationId: string) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const wsUrl = apiUrl.replace(/^http/, 'ws') + `/handoff/ws/user/${conversationId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'agent_assigned') {
        setAgentId(data.agent_id);
      } else if (data.type === 'offer') {
        await handleOffer(data.payload, data.agent_id);
      } else if (data.type === 'ice-candidate') {
        if (peerConnectionRef.current) {
          await peerConnectionRef.current.addIceCandidate(new RTCIceCandidate(data.payload));
        }
      } else if (data.type === 'chat_message') {
        if (!dataChannelRef.current || dataChannelRef.current.readyState !== 'open') {
          setMessages(prev => [...prev, {
            id: Math.random().toString(),
            sender: 'human_agent',
            text: data.message,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }]);
        }
      }
    };
  };

  const handleOffer = async (offer: RTCSessionDescriptionInit, agentId: string) => {
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });
    peerConnectionRef.current = pc;

    pc.onicecandidate = (event) => {
      if (event.candidate && wsRef.current) {
        wsRef.current.send(JSON.stringify({
          type: 'ice-candidate',
          payload: event.candidate,
          agent_id: agentId
        }));
      }
    };

    pc.ondatachannel = (event) => {
      const channel = event.channel;
      dataChannelRef.current = channel;
      
      channel.onmessage = (e) => {
        setMessages(prev => [...prev, {
          id: Math.random().toString(),
          sender: 'human_agent',
          text: e.data,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
      };
      
      channel.onopen = () => {
        setIsConnectedToAgent(true);
        console.log("Data channel opened from user");
      };
      
      channel.onclose = () => {
        setIsConnectedToAgent(false);
        setIsHandedOver(false);
        setMessages(prev => [...prev, {
          id: Math.random().toString(),
          sender: 'ai', // treating system message as AI
          text: 'The agent has ended the chat.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
      };
    };

    await pc.setRemoteDescription(new RTCSessionDescription(offer));
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);

    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({
        type: 'answer',
        payload: answer,
        agent_id: agentId
      }));
    }
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

    if (isHandedOver) {
      if (dataChannelRef.current && dataChannelRef.current.readyState === 'open') {
        dataChannelRef.current.send(userText);
        wsRef.current?.send(JSON.stringify({
          type: 'chat_message',
          message: userText,
          agent_id: agentId
        }));
      } else {
        wsRef.current?.send(JSON.stringify({
          type: 'chat_message',
          message: userText,
          agent_id: agentId
        }));
      }
      return;
    }

    setIsTyping(true);

    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
      if (!token) throw new Error("No token found");

      const updatedConv = await sendMessage(token, userText, activeConversationId);
      
      if (updatedConv.messages) {
        // Normal conversation update
        setActiveConversationId(updatedConv.cid);
        if (updatedConv.status?.toLowerCase() === 'handed_over') {
           setIsHandedOver(true);
           if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
             connectWebSocket(updatedConv.cid);
           }
        }
        const formattedMsgs = updatedConv.messages.map((m: any) => ({
          id: m.mid,
          sender: m.sender_type?.toUpperCase() === 'BOT' || m.sender_type?.toUpperCase() === 'AI' ? 'ai' : (m.sender_type?.toUpperCase() === 'HUMAN_AGENT' ? 'human_agent' : 'user'),
          text: m.message_text,
          time: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
        }));
        setMessages(formattedMsgs);

        setAllConversations(prev => {
          const index = prev.findIndex(c => c.cid === updatedConv.cid);
          if (index >= 0) {
            const newAll = [...prev];
            newAll[index] = updatedConv;
            return newAll;
          } else {
            return [updatedConv, ...prev];
          }
        });
      } else {
        // Raw JSON classification response
        const subIntents = updatedConv.sub_intents && updatedConv.sub_intents.length > 0 
          ? updatedConv.sub_intents.join(', ') 
          : 'None';
          
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          sender: 'ai',
          text: `[Classification] Intent: ${updatedConv.intent} | Sub-intents: ${subIntents} | Confidence: ${updatedConv.confidence}%`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
      }
    } catch (err) {
      console.error("Failed to send message", err);
    } finally {
      setIsTyping(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        handleSendAudio(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Error accessing microphone:", err);
      alert("Could not access microphone.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
      setIsRecording(false);
    }
  };

  const handleSendAudio = async (audioBlob: Blob) => {
    setIsTyping(true);
    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
      if (!token) throw new Error("No token found");

      const updatedConv = await sendAudioMessage(token, audioBlob, activeConversationId);
      
      if (updatedConv.messages) {
        setActiveConversationId(updatedConv.cid);
        if (updatedConv.status?.toLowerCase() === 'handed_over') {
           setIsHandedOver(true);
           if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
             connectWebSocket(updatedConv.cid);
           }
        }
        const formattedMsgs = updatedConv.messages.map((m: any) => ({
          id: m.mid,
          sender: m.sender_type?.toUpperCase() === 'BOT' || m.sender_type?.toUpperCase() === 'AI' ? 'ai' : (m.sender_type?.toUpperCase() === 'HUMAN_AGENT' ? 'human_agent' : 'user'),
          text: m.message_text,
          time: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
        }));
        setMessages(formattedMsgs);

        setAllConversations(prev => {
          const index = prev.findIndex(c => c.cid === updatedConv.cid);
          if (index >= 0) {
            const newAll = [...prev];
            newAll[index] = updatedConv;
            return newAll;
          } else {
            return [updatedConv, ...prev];
          }
        });
      } else {
        const subIntents = updatedConv.sub_intents && updatedConv.sub_intents.length > 0 
          ? updatedConv.sub_intents.join(', ') 
          : 'None';
          
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          sender: 'ai',
          text: `[Classification] Intent: ${updatedConv.intent} | Sub-intents: ${subIntents} | Confidence: ${updatedConv.confidence}%`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
      }
    } catch (err) {
      console.error("Failed to send audio message", err);
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
    <div className={`${styles.container} ${isLightMode ? styles.lightMode : ''}`}>
      {/* Sidebar */}
      <div className={styles.sidebar}>
        <div className={styles.logo}>SOA</div>
        
        <button className={styles.newChatBtn} onClick={() => {
          setActiveConversationId(null);
          setIsHandedOver(false);
          setIsConnectedToAgent(false);
          setAgentId(null);
          if (dataChannelRef.current) dataChannelRef.current.onclose = null;
          if (wsRef.current) wsRef.current.close();
          if (peerConnectionRef.current) peerConnectionRef.current.close();
          wsRef.current = null;
          peerConnectionRef.current = null;
          dataChannelRef.current = null;
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
              const firstUserMsg = conv.messages?.find((m: any) => m.sender_type?.toUpperCase() === 'USER' || m.sender_type === 'user');
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
                  key={conv.cid} 
                  className={styles.historyItem} 
                  style={{ background: activeConversationId === conv.cid ? 'rgba(255,255,255,0.05)' : 'transparent' }}
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
          <button className={styles.contactBtn} onClick={() => {
            const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
            if (!token) return;
            const text = "connect me to an agent";
            setMessages(prev => [...prev, {
              id: Date.now().toString(),
              sender: 'user',
              text: text,
              time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }]);
            setIsTyping(true);
            sendMessage(token, text, activeConversationId).then(updatedConv => {
              if (updatedConv.messages) {
                setActiveConversationId(updatedConv.cid);
                if (updatedConv.status?.toLowerCase() === 'handed_over') {
                   setIsHandedOver(true);
                   if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
                     connectWebSocket(updatedConv.cid);
                   }
                }
                const formattedMsgs = updatedConv.messages.map((m: any) => ({
                  id: m.mid,
                  sender: m.sender_type?.toUpperCase() === 'BOT' || m.sender_type?.toUpperCase() === 'AI' ? 'ai' : (m.sender_type?.toUpperCase() === 'HUMAN_AGENT' ? 'human_agent' : 'user'),
                  text: m.message_text,
                  time: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
                }));
                setMessages(formattedMsgs);
              }
            }).finally(() => setIsTyping(false));
          }}>
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
          <div className={styles.headerTitle} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sparkles size={20} color="#7c5dfa" /> AI Support Assistant
            {isHandedOver && (
              <span style={{ 
                fontSize: '14px', 
                padding: '6px 12px', 
                borderRadius: '16px', 
                backgroundColor: isConnectedToAgent ? '#dcfce7' : '#fee2e2',
                color: isConnectedToAgent ? '#166534' : '#991b1b',
                fontWeight: '500'
              }}>
                {isConnectedToAgent ? 'Connected to Agent' : 'Waiting for Agent...'}
              </span>
            )}
          </div>
          <div className={styles.headerActions}>
            <button className={styles.viewOrdersBtn} onClick={() => router.push('/orders')}>
              <ShoppingBag size={16} /> View Orders
            </button>
            <button className={styles.iconBtn} onClick={() => setIsLightMode(!isLightMode)}>
              {isLightMode ? <Moon size={18} /> : <Sun size={18} />}
            </button>
          </div>
        </div>

        {/* Chat Container */}
        <div className={styles.chatContainer}>
          {messages.map((msg) => (
            <div key={msg.id} className={`${styles.messageRow} ${(msg.sender === 'ai' || msg.sender === 'human_agent') ? styles.ai : styles.user}`}>
              {(msg.sender === 'ai' || msg.sender === 'human_agent') && (
                <div className={styles.aiAvatar}>
                  {msg.sender === 'human_agent' ? <Headphones size={20} color="#fff" /> : <Sparkles size={20} color="#fff" />}
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
              <button 
                className={isRecording ? `${styles.audioBtn} ${styles.recording}` : styles.audioBtn}
                onClick={isRecording ? stopRecording : startRecording}
              >
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
