import { useCallback, useState } from "react";
import { chatManager } from "../services/manager";
import { ManagerChatResponse, ConversationMessage } from "../types/ai";

export function useManagerChat() {
  const [loading, setLoading] = useState(false);
  const [typing, setTyping] = useState(false);

  const send = useCallback(async (message: string, conversationId?: string): Promise<ManagerChatResponse> => {
    setLoading(true);
    setTyping(true);
    try {
      const resp = await chatManager(message, conversationId);
      return resp;
    } finally {
      setTyping(false);
      setLoading(false);
    }
  }, []);

  return { send, loading, typing };
}