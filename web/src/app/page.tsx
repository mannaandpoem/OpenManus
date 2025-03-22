'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { Message } from '@/types/chat';
import { ChatMessage } from '@/components/features/chat/ChatMessage';
import { createTask, getTaskEvents, handleTaskEventsStreamResponse } from '@/services/task';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Send } from 'lucide-react';
import Image from 'next/image';
import logo from '@/assets/logo.png';

const EmptyState = () => (
  <div className="flex flex-col items-center justify-center h-full opacity-50">
    <Image src={logo} alt="OpenManus" className="mb-4 object-contain" width={240} height={240} />
    <div>No fortress, purely open ground. OpenManus is Coming.</div>
  </div>
);

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const isNearBottom = () => {
    if (!messagesContainerRef.current) return false;
    const container = messagesContainerRef.current;
    const threshold = 100;
    return container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
  };

  const scrollToBottom = () => {
    if (isNearBottom()) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const updateLastMessage = (content: string, type?: string, step?: number) => {
    setMessages(prev => {
      const newMessages = [...prev];
      const lastMessage = newMessages[newMessages.length - 1];
      lastMessage.content = content;
      if (type) lastMessage.type = type as any;
      if (step !== undefined) lastMessage.step = step;
      return newMessages;
    });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const { task_id } = await createTask(input, abortControllerRef.current.signal);
      const eventsResponse = await getTaskEvents(task_id, abortControllerRef.current.signal);

      await handleTaskEventsStreamResponse(eventsResponse, messages => {
        setMessages([userMessage, ...messages]);
      });
    } catch (error: any) {
      if (error.name === 'AbortError') {
        return;
      }
      console.error('Error:', error);
      updateLastMessage('Sorry, an error occurred. Please try again later.');
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 pb-20 space-y-4">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            {messages.map((message, index) => (
              <ChatMessage key={`${index}-${message.content}`} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <div className="fixed bottom-0 left-0 right-0 p-4 pointer-events-none">
        <form onSubmit={handleSubmit} className="container max-w-2xl mx-auto pointer-events-auto">
          <div className="relative flex bg-white rounded-2xl shadow-[0_0_15px_rgba(0,0,0,0.1)]">
            <Input
              value={isLoading ? 'Thinking...' : input}
              aria-disabled={isLoading}
              onChange={e => setInput(e.target.value)}
              placeholder="Let's Imagine the Impossible, Create the Future Together"
              className="flex-1 border-0 focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent h-12 px-4"
              disabled={isLoading}
            />
            <Button
              type="submit"
              disabled={isLoading}
              size="icon"
              variant="ghost"
              className="absolute cursor-pointer right-1 top-1/2 -translate-y-1/2 h-10 w-10 hover:bg-gray-100 rounded-xl"
            >
              <Send className="h-5 w-5" />
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
