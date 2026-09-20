/**
 * A deliberately tiny Java tokenizer, for display only.
 *
 * This is not a parser and must never become one — the backend owns all
 * understanding of the program. Its only job is to give the code panel enough
 * structure to colour, and it is written so that concatenating every token's
 * `text` reproduces the input exactly, byte for byte. Anything it cannot
 * classify falls through to `plain` rather than being dropped.
 *
 * The palette is three hues on purpose. Beginners are already decoding the
 * language; a twelve-colour theme adds a second decoding problem on top.
 * `TOKEN_CLASS` is exported rather than inlined because ValueChip renders
 * literals with the same classes — a `5` in the stack and a `5` in the source
 * are the same value, so they had better be the same colour.
 */

export type TokenKind =
  | "keyword"
  | "type"
  | "string"
  | "number"
  | "comment"
  | "punct"
  | "plain";

export interface Token {
  text: string;
  kind: TokenKind;
}

export const TOKEN_CLASS: Record<TokenKind, string> = {
  keyword: "text-code-keyword",
  type: "text-code-type",
  string: "text-code-string",
  number: "text-code-type",
  comment: "text-code-comment italic",
  punct: "text-ink-faint",
  plain: "text-ink",
};

const KEYWORDS = new Set([
  "abstract", "assert", "break", "case", "catch", "class", "const", "continue",
  "default", "do", "else", "enum", "extends", "final", "finally", "for", "goto",
  "if", "implements", "import", "instanceof", "interface", "native", "new",
  "package", "private", "protected", "public", "return", "static", "strictfp",
  "super", "switch", "synchronized", "this", "throw", "throws", "transient",
  "try", "volatile", "while", "true", "false", "null",
]);

const TYPES = new Set([
  "int", "long", "short", "byte", "double", "float", "boolean", "char", "void",
  "var", "String",
]);

/*
 * Order matters: comments before strings before numbers before words. The final
 * `[\s\S]` alternative guarantees every character is consumed exactly once.
 * Unterminated strings use an optional closing quote so that a half-typed line
 * still tokenizes instead of swallowing the rest of the file.
 */
const TOKEN_RE =
  /(\/\/[^\n]*)|(\/\*[\s\S]*?(?:\*\/|$))|("(?:\\.|[^"\\\n])*"?)|('(?:\\.|[^'\\\n])*'?)|(\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?[fFdDlL]?)|([A-Za-z_$][A-Za-z0-9_$]*)|([\s\S])/g;

function classifyWord(word: string): TokenKind {
  if (KEYWORDS.has(word)) return "keyword";
  if (TYPES.has(word)) return "type";
  // Capitalised identifiers are types by convention in Java, which is exactly
  // the convention we want a beginner to start noticing.
  if (/^[A-Z]/.test(word)) return "type";
  return "plain";
}

export function tokenize(line: string): Token[] {
  const tokens: Token[] = [];
  const push = (text: string, kind: TokenKind) => {
    // Merge runs of the same kind so the DOM stays small and selection behaves.
    const last = tokens[tokens.length - 1];
    if (last && last.kind === kind) last.text += text;
    else tokens.push({ text, kind });
  };

  for (const match of line.matchAll(TOKEN_RE)) {
    const [text, lineComment, blockComment, str, char, num, word, other] = match;
    if (lineComment !== undefined || blockComment !== undefined) push(text, "comment");
    else if (str !== undefined || char !== undefined) push(text, "string");
    else if (num !== undefined) push(text, "number");
    else if (word !== undefined) push(text, classifyWord(word));
    else if (other !== undefined && /\s/.test(other)) push(text, "plain");
    else push(text, "punct");
  }

  return tokens;
}
