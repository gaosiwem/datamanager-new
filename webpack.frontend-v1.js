const { resolve } = require("path");

module.exports = {
  mode: "production",
  entry: {
    "frontend-v1": "./assets/js/scripts.js",
  },
  output: {
    path: resolve(__dirname, "assets/generated/"),
    filename: "[name].bundle.js",
  },
  devtool: "source-map",
  module: {
    rules: [
      {
        test: /\.html$/,
        exclude: /node_modules/,
        use: { loader: "html-loader" },
      },
      {
        test: /\.jsx?$/,
        loader: "babel-loader",
        options: {
          presets: ["react"],
        },
      },
      {
        test: /\.s?css$/,
        use: [resolve(__dirname, "build/ignore-style-loader.js")],
      },
    ],
  },
};
