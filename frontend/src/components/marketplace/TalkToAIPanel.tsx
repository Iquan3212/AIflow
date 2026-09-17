import { Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";

import Modal from "../ui/Modal";
import AssistantChat from "./AssistantChat";

/** The quick-question modal opened from a property/project card - full
 * chat logic lives in AssistantChat (shared with the dedicated
 * /buyer/assistant page), this just frames it as a modal and offers a
 * way to continue the same kind of conversation full-page. */
export default function TalkToAIPanel({
    agencySlug,
    agencyName,
    propertyId,
    contextLabel,
    onClose,
}: {
    agencySlug: string;
    agencyName: string;
    propertyId?: string;
    contextLabel?: string;
    onClose: () => void;
}) {
    return (
        <Modal title={`Ask ${agencyName}'s AI Assistant`} onClose={onClose}>
            <AssistantChat agencySlug={agencySlug} agencyName={agencyName} propertyId={propertyId} contextLabel={contextLabel} compact />
            <Link
                to={propertyId ? `/buyer/assistant?propertyId=${propertyId}` : "/buyer/assistant"}
                onClick={onClose}
                className="mt-3 flex items-center justify-center gap-1.5 text-xs font-medium text-brand-600 hover:text-brand-700"
            >
                Open full assistant <ExternalLink size={12} aria-hidden="true" />
            </Link>
        </Modal>
    );
}
