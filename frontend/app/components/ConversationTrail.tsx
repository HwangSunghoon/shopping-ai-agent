"use client";

type ConversationTrailProps = {
  items: Array<{
    question: string;
    answer: string;
  }>;
  compact?: boolean;
};

export function ConversationTrail({ items, compact = false }: ConversationTrailProps) {
  if (items.length === 0) return null;

  return (
    <section className={`conversationTrail ${compact ? "compactTrail" : ""}`}>
      {items.slice(-4).map((item, index) => (
        <div key={`${item.question}-${index}`} className="trailThread">
          <div className="trailItem userTrailItem">
            <p>{item.question}</p>
          </div>
          <div className="trailItem subtle assistantTrailItem">
            <p>{item.answer}</p>
          </div>
        </div>
      ))}
    </section>
  );
}
