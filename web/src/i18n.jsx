import { createContext, useContext } from "react";

export const EN = {
  brandSubtitle: "Digitizing Sino–Nom heritage",
  mainNav: "Main navigation", recognize: "Recognize", scanHistory: "Scan history",
  downloadApp: "Download app", downloadAppTitle: "Download the Mộc Bản OCR mobile app (via Google Drive)",
  lightMode: "Switch to light mode", darkMode: "Switch to dark mode", themeLabel: "Toggle light/dark mode",
  apiSettings: "API server settings", account: "Account", logout: "Log out", login: "Log in",
  language: "Change language", english: "English", vietnamese: "Vietnamese",
  close: "Close", closeNotice: "Dismiss notification", cancel: "Cancel", delete: "Delete",
  serverSettings: "Server settings", serverAddress: "OCR server address (API)", check: "Check",
  serverOk: "The server is running normally.", serverDown: "Cannot connect to the server — check whether Docker is running.",
  checkingConnection: "Checking connection…", notChecked: "Not checked yet.",
  settingsHint: "The default value comes from the VITE_API_BASE environment variable at build time. Changes here apply only to the current browser.",
  createAccount: "Create account", fullName: "Full name", fullNameExample: "Example: John Smith",
  phone: "Phone number", optional: "Optional", email: "Email address", password: "Password",
  processing: "Processing…", registerAccount: "Create account", orGoogle: "Or sign in with",
  noAccount: "Don't have an account?", registerNow: "Register now", haveAccount: "Already have an account?",
  historyTitle: "Document scan history", loadingHistory: "Loading history…",
  noHistory: "No documents have been saved. Run OCR in the Recognize tab, then choose Save to account.",
  open: "Open", document: "Document", empty: "Empty", deleteDocument: "Delete document",
  chooseAnother: "Choose another image", removeImage: "Remove image", chooseImage: "Choose image…",
  preprocess: "Preprocess", preprocessTitle: "Run preprocessing only to preview the image", runOcr: "Run OCR",
  aiProof: "AI correction", aiProofTitle: "After OCR, use SikuBERT to correct Sino–Nom text (takes about twice as long)",
  update: "Update", saveAccount: "Save to account", chars: "characters", columns: "columns",
  advanced: "Advanced preprocessing options", enablePreprocess: "Enable preprocessing", inputStage: "OCR input stage",
  flip: "Flip image", denoise: "Noise reduction", resizeWidth: "Resize width", deskew: "Deskew (±°)", defaults: "Reset defaults",
  flipWhyTitle: "Why is horizontal flip the default?", flipWhy: "A direct photo of a woodblock contains mirrored text. Horizontal flip restores the correct reading direction. For a paper print, set flip to none.",
  splitLabel: "Drag to resize the two panels", splitTitle: "Drag to resize · double-click to reset",
  saveResult: "Save OCR result", documentTitle: "Document title", titleExample: "Example: Woodblock page 3",
  saving: "Saving…", saveServer: "Save to server", lockSubtitle: "Sino–Nom heritage digitization system",
  lockPrefix: "Please", lockOr: "or", lockSuffix: "to use the service.", register: "register",
  woodblockImage: "Woodblock image", processed: "Processed", originalImage: "Original image",
  zoomOut: "Zoom out", zoomIn: "Zoom in", actualSize: "View actual size (100%)", fit: "Fit to panel",
  hideBoxes: "Hide text boxes", showBoxes: "Show text boxes", dropTitle: "Drop a woodblock image here",
  dropSub: "or click to choose an image", processingImage: "Processing image…", preprocessingImage: "Preprocessing image…",
  recognizing: "Recognizing Chinese characters…", aiCorrecting: "Correcting with SikuBERT…", lineBoxes: "Line boxes:",
  below60: "Below 60%", charBelow60: "Character < 60%", aiFixed: "AI corrected",
  resultProof: "Results & correction", noRecognized: "No text was recognized in the image. Try adjusting preprocessing parameters.",
  noData: "No recognition data yet. Upload an image and click Run OCR.", originalOcr: "Original OCR", aiCorrected: "AI corrected",
  byColumn: "By column", list: "List", column: "Column", confidence: "confidence", editLineTitle: "Edit entire line / move column",
  editLine: "Edit line", lineContent: "Line content", columnNumber: "Column number", saveLine: "Save line",
  chooseCorrect: "Choose the correct character", noSuggestions: "No suggestions for this character.",
  enterOther: "Enter another character…", replacementChar: "Enter replacement character", apply: "Apply", restoreOriginal: "Restore original",
  fullText: "Full text", copy: "Copy", copied: "Full text copied", copyFailed: "Could not copy", clipboardBlocked: "The browser blocked clipboard access.",
  aiChangedCount: "SikuBERT corrected {count} characters", aiChangedTitle: "Number of characters SikuBERT changed from the original OCR",
  downloadTxt: "Download the current full text as .txt", downloadJson: "Download the full result (lines, columns, confidence) as .json",
  rawOcr: "Raw OCR", manuallyEdited: "Manually edited", clickCorrect: "Click to correct", original: "Original",
  savedDocument: "Saved document", angle: "angle",
  welcome: "Welcome", registerSuccess: "Registration successful", registerSuccessSub: "Sign in with your new account.",
  sessionExpired: "Your session has expired", loginAgain: "Please sign in again.", invalidFile: "Invalid file", chooseImageFile: "Please choose an image file.",
  saved: "Document saved", saveFailed: "Could not save", updated: "Changes updated", updateFailed: "Update failed",
  confirmDelete: "Delete document", confirmDeleteText: "Permanently delete “{title}” from your account?", deleted: "Document deleted", deleteFailed: "Could not delete",
  openFailed: "Could not open document", imageFailed: "Could not load the original image", imageFailedSub: "The saved text will still be displayed.",
  aiUnavailable: "SikuBERT is not ready", aiUnavailableSub: "The server returned the original OCR result (the post-processing model is not loaded).",
  aiNoErrors: "SikuBERT found no errors to correct", aiFailed: "AI correction failed",
  appTitle: "Mộc Bản OCR — Sino–Nom heritage digitization",
};

export const I18nContext = createContext({ language: "vi", t: (_key, vi) => vi });
export const useI18n = () => useContext(I18nContext);

export function makeTranslator(language) {
  return (key, vi, vars) => {
    let value = language === "en" ? (EN[key] ?? vi ?? key) : (vi ?? key);
    if (vars) Object.entries(vars).forEach(([name, replacement]) => { value = value.replaceAll(`{${name}}`, replacement); });
    return value;
  };
}
