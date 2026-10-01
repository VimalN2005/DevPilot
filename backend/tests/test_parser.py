import pytest
from app.services.code_parser import code_parser


def test_python_ast_parsing():
    sample_code = """
import os
import sys

class AuthService:
    def __init__(self, secret: str):
        self.secret = secret

    def verify_token(self, token: str) -> bool:
        return True

def standalone_helper():
    return "ok"
"""
    chunks = code_parser.parse_python("sample_auth.py", sample_code)
    assert len(chunks) >= 3

    symbols = [c.symbol_name for c in chunks]
    assert "AuthService" in symbols
    assert "standalone_helper" in symbols

    types = [c.symbol_type for c in chunks]
    assert "class" in types
    assert "function" in types


def test_generic_chunker():
    js_code = """
function calculateMetrics(data) {
    return data.length * 10;
}
"""
    chunks = code_parser.parse_file("metrics.js", js_code)
    assert len(chunks) >= 1
    assert chunks[0].language == "javascript"


def test_typescript_and_go_structural_parsing():
    ts_code = """
export interface UserPayload {
    id: string;
    role: string;
}

export class TokenManager {
    generateToken(user: UserPayload): string {
        return "jwt-token";
    }
}

export const verifySession = (token: string) => {
    return token.length > 0;
};
"""
    chunks = code_parser.parse_file("session.ts", ts_code)
    symbols = [c.symbol_name for c in chunks]
    assert "UserPayload" in symbols
    assert "TokenManager" in symbols
    assert "verifySession" in symbols
