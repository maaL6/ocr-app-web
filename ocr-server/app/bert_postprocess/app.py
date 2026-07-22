from fastapi import FastAPI, HTTPException
from postprocess_ocr import OCRPostProcessor
import uvicorn

app = FastAPI(
    title="SikuBERT OCR Post-Correction API",
    description="REST API for post-processing and correcting CJK Han Nom OCR output using SikuBERT."
)

# Initialize the postprocessor once during startup to preload the model into RAM/VRAM
processor = OCRPostProcessor(mode="candidate_reranking")

@app.post("/correct")
def correct_ocr(payload: dict):
    """
    Accepts raw OCR JSON, processes it using SikuBERT candidate reranking,
    and returns the corrected text/confidence values conforming to the clean OCR schema.
    """
    try:
        # Process the input payload
        result = processor.process(payload)
        # Apply the clean public OCR schema filtering
        clean_result = processor.to_ocr_schema(result)
        return clean_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")

@app.get("/health")
def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
