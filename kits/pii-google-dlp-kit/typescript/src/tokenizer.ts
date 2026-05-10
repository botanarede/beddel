import type { IPIITokenizer } from "../../../src/domain/ports.js";

/**
 * Google Cloud DLP PII tokenizer.
 * Delegates PII detection to the Google Cloud DLP API for enterprise-grade detection.
 * Requires @google-cloud/dlp as a peer dependency.
 *
 * @implements {IPIITokenizer}
 */
export class GoogleDLPTokenizer implements IPIITokenizer {
	tokenize(_text: string): [string, Record<string, string>] {
		throw new Error("GoogleDLPTokenizer not yet implemented — install @google-cloud/dlp and configure credentials");
	}

	detokenize(_text: string, _tokenMap: Record<string, string>): string {
		throw new Error("GoogleDLPTokenizer not yet implemented");
	}
}
