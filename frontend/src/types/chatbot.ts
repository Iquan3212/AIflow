export interface ChatbotConfig {

    id: string;

    business_id: string;

    welcome_message: string;

    persona_tone: string;

    business_description: string;

    faqs: {
        question: string;
        answer: string;
    }[];

    services: string[];

    lead_questions: string[];

    updated_at: string;
}