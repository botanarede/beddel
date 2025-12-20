module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  testMatch: ["**/tests/{agents,runtime,security}/**/*.test.ts"],
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json", "node"],
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: "<rootDir>/tsconfig.jest.json",
      },
    ],
  },
  testPathIgnorePatterns: [
    "<rootDir>/tests/agents/validator-agent.test.ts",
  ],
  // Mock server-only package for Jest (it's a Next.js-specific package)
  moduleNameMapper: {
    "^server-only$": "<rootDir>/tests/__mocks__/server-only.js",
  },
  clearMocks: true,
};
