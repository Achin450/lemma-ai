from pydantic import BaseModel, Field

class RewriteRequest(BaseModel):
    text: str = Field(..., description="The sentence or text segment to rewrite.")
    tone: str | None = Field("academic", description="The tone: 'academic', 'standard', 'formal', 'creative', 'shorten', or 'expand'.")

class RewriteResponse(BaseModel):
    original_text: str = Field(..., description="The original text segment before rewriting.")
    rewritten_text: str = Field(..., description="The paraphrased/rewritten text segment.")
    tone: str | None = Field("academic", description="The tone used for paraphrasing.")
    words_original: int | None = Field(0, description="Word count of original text.")
    words_rewritten: int | None = Field(0, description="Word count of rewritten text.")

class HumanizeRequest(BaseModel):
    text: str = Field(..., description="The AI-generated text to humanize.")
    tone: str | None = Field("academic", description="The humanization style: 'academic', 'stealth', 'formal', 'natural'.")
    intensity: str | None = Field("high", description="Humanization intensity: 'standard', 'high', 'maximum'.")

class HumanizeResponse(BaseModel):
    original_text: str = Field(..., description="Original input text.")
    humanized_text: str = Field(..., description="Humanized output text with high burstiness and zero AI clichés.")
    tone: str = Field("academic", description="Applied humanization tone.")
    words_original: int = Field(0, description="Word count before.")
    words_humanized: int = Field(0, description="Word count after.")
    ai_score_before: float = Field(0.95, description="Estimated AI probability before humanization.")
    ai_score_after: float = Field(0.08, description="Estimated AI probability after humanization.")

