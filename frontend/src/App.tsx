import {
  Avatar,
  ChatContainer,
  Conversation,
  ConversationHeader,
  ConversationList,
  MainContainer,
  Message,
  MessageInput,
  MessageList,
  Sidebar,
} from "@chatscope/chat-ui-kit-react";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import axios, { AxiosRequestConfig } from "axios";
import { CSSProperties, useCallback, useEffect, useState } from "react";
import { Container, Image, Nav, NavDropdown, Navbar } from "react-bootstrap";
import Linkify from "react-linkify";
import { format } from "timeago.js";
import useLocalStorageState from "use-local-storage-state";

import "bootstrap/dist/css/bootstrap.min.css";
import "./App.css";

namespace Chatweb {
  export interface Contact {
    id: string;
    name: string;
    avatar: string;
  }

  export interface Conversation {
    id: string;
    name: string;
    avatar: string;
    last_active: string | null;
  }

  export interface Message {
    body: string;
    sender: string;
    timestamp: string;
  }

  export interface Provider {
    id: string;
    name: string;
    icon: string;
  }
}

export default function App() {
  const [providerId, setProviderId] = useLocalStorageState<string>("providerId");
  const [providers, setProviders] = useLocalStorageState<Chatweb.Provider[]>("providers");
  const [me, setMe] = useState<Chatweb.Contact>();
  const [contacts, setContacts] = useState<Chatweb.Contact[]>();
  const [conversations, setConversations] = useState<Chatweb.Conversation[]>();
  const [activeConversation, setActiveConversation] = useState<Chatweb.Conversation>();
  const [sidebarStyle, setSidebarStyle] = useState<CSSProperties>();
  const [messages, setMessages] = useState<Chatweb.Message[]>();

  const getApi = useCallback(
    async (url: string, config?: AxiosRequestConfig) => {
      const { data } = await axios.get(url, {
        headers: {
          "provider-id": providerId,
        },
        ...config,
      });
      return data;
    },
    [providerId]
  );

  useEffect(() => {
    const fetchProviders = async () => {
      const { data } = await axios.get("/api/providers");
      setProviders(data as Chatweb.Provider[]);
    };

    fetchProviders();
  }, [getApi, setProviders]);

  useEffect(() => {
    const fetchMe = async () => {
      const data = await getApi("/api/whoami");
      setMe(data as Chatweb.Contact);
    };

    if (providerId) {
      fetchMe().catch(console.error);
    } else {
      setMe(undefined);
    }
  }, [providerId, getApi]);

  useEffect(() => {
    const fetch_contacts = async () => {
      const data = await getApi("/api/contacts");

      const contacts = data as Chatweb.Contact[];
      setContacts(contacts);
    };

    if (providerId) {
      fetch_contacts().catch(console.error);
    } else {
      setContacts(undefined);
    }
  }, [providerId, getApi]);

  useEffect(() => {
    const fetchConversations = async () => {
      const data = await getApi("/api/conversations");

      const conversations = data as Chatweb.Conversation[];
      setConversations(conversations);
    };

    if (providerId) {
      fetchConversations().catch(console.error);
    } else {
      setConversations(undefined);
    }
  }, [providerId, getApi]);

  const fetchMessages = useCallback(async () => {
    if (activeConversation != null) {
      const data = await getApi("/api/messages", {
        params: {
          conversation_id: activeConversation.id,
        },
      });
      setMessages(data);
    }
  }, [activeConversation, getApi]);

  useEffect(() => {
    setMessages(undefined);
    fetchMessages();
  }, [activeConversation, fetchMessages]);

  useEffect(() => {
    if (activeConversation) {
      setSidebarStyle(undefined);
    } else {
      setSidebarStyle({
        display: "flex",
        flexBasis: "auto",
        width: "100%",
        maxWidth: "100%",
      });
    }
  }, [activeConversation]);

  const sendMessage = async (body: string) => {
    await axios.post(
      "/api/messages",
      {
        conversation_id: activeConversation?.id,
        body,
      },
      {
        headers: {
          "provider-id": providerId,
        },
      }
    );

    await fetchMessages();
  };

  const updateProviderId = async (newProviderId: string) => {
    if (newProviderId !== providerId) {
      setActiveConversation(undefined);
      setMe(undefined);
      setContacts(undefined);
      setConversations(undefined);
      setMessages(undefined);
      setProviderId(newProviderId);
    }
  };

  const renderProvider = (provider: Chatweb.Provider | undefined) => {
    if (!provider) {
      return "Select...";
    } else {
      return (
        <Image style={{ width: "32px", height: "32px" }} src={provider.icon} alt={provider.name} />
      );
    }
  };

  return (
    <Container className="d-flex flex-column" style={{ position: "absolute", inset: "5px" }}>
      <Navbar collapseOnSelect expand="md">
        <Container fluid>
          <Navbar.Brand>Chatweb</Navbar.Brand>
          <Nav>
            <NavDropdown title={renderProvider(providers?.find((p) => p.id === providerId))}>
              {providers?.map((provider) => (
                <NavDropdown.Item onClick={() => updateProviderId(provider.id)}>
                  {renderProvider(provider)}
                  <span className="ms-2">{provider.name}</span>
                </NavDropdown.Item>
              ))}
            </NavDropdown>
          </Nav>
        </Container>
      </Navbar>
      <MainContainer responsive>
        <Sidebar position="left" style={sidebarStyle}>
          <ConversationList loading={conversations === undefined}>
            {conversations?.map((conversation) => (
              <Conversation
                name={conversation.name}
                onClick={() => setActiveConversation(conversation)}
                active={conversation === activeConversation}
                lastActivityTime={
                  conversation.last_active ? format(conversation.last_active) : null
                }
                style={{ display: "flex" }}
              >
                <Avatar src={conversation.avatar} name={conversation.name} />
              </Conversation>
            ))}
          </ConversationList>
        </Sidebar>
        {activeConversation && (
          <ChatContainer>
            <ConversationHeader>
              <ConversationHeader.Back onClick={() => setActiveConversation(undefined)} />
              <Avatar src={activeConversation.avatar} name={activeConversation.name} />
              <ConversationHeader.Content userName={activeConversation.name} />
            </ConversationHeader>
            <MessageList loading={messages === undefined}>
              {messages?.map((message) => {
                const direction = message.sender === me?.id ? "outgoing" : "incoming";
                const sender =
                  direction === "incoming" ? contacts?.find((c) => c.id === message.sender) : me;
                return (
                  <Message
                    model={{
                      type: "custom",
                      sentTime: format(message.timestamp),
                      sender: sender?.name,
                      direction,
                      position: "normal",
                    }}
                  >
                    <Message.CustomContent>
                      <Linkify>{message.body}</Linkify>
                    </Message.CustomContent>
                    <Message.Footer sender={sender?.name} sentTime={format(message.timestamp)} />
                    {sender && <Avatar src={sender.avatar} name={sender.name} />}
                  </Message>
                );
              })}
            </MessageList>
            <MessageInput
              placeholder="Type message here"
              onSend={(_, textContent) => sendMessage(textContent)}
            />
          </ChatContainer>
        )}
      </MainContainer>
    </Container>
  );
}
