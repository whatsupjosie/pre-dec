module.exports = {
  testEnvironment: "node",
  testMatch: ["**/test/**/*.test.js"],
  moduleNameMapper: {
    "^electron$":       "<rootDir>/test/mocks/electron.js",
    "^electron-store$": "<rootDir>/test/mocks/electron-store.js",
  },
  testTimeout: 15000,
};
