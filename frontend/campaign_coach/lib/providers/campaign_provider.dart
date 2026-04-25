import 'package:flutter/material.dart';

class CampaignProvider extends ChangeNotifier {
  String rawContext = '';
  String productUrl = '';
  bool generateExamples = true;
  bool useKnowledgeBase = false;
  bool isGenerating = false;
  bool isAnalyzingUrl = false;
  bool isGeneratingImages = false;

  int numImages = 2;

  Map<String, String> outputs = {};
  Map<String, String> outputFileUrls = {};
  List<String> generatedImagePaths = [];
  List<Map<String, String>> chatHistory = [];

  List<String> kbFiles = [];
  List<String> mediaFiles = [];

  void updateContext(String value) {
    rawContext = value;
    notifyListeners();
  }

  void updateProductUrl(String value) {
    productUrl = value;
    notifyListeners();
  }

  void toggleExamples(bool value) {
    generateExamples = value;
    notifyListeners();
  }

  void toggleKnowledgeBase(bool value) {
    useKnowledgeBase = value;
    notifyListeners();
  }

  void setGenerating(bool value) {
    isGenerating = value;
    notifyListeners();
  }

  void setAnalyzingUrl(bool value) {
    isAnalyzingUrl = value;
    notifyListeners();
  }

  void setGeneratingImages(bool value) {
    isGeneratingImages = value;
    notifyListeners();
  }

  void setNumImages(double value) {
    numImages = value.round().clamp(1, 4);
    notifyListeners();
  }

  void updateOutputs(
    Map<String, String> newOutputs, {
    Map<String, String>? newOutputFileUrls,
  }) {
    outputs = newOutputs;
    outputFileUrls = newOutputFileUrls ?? {};
    chatHistory.clear();
    notifyListeners();
  }

  void addGeneratedImages(List<String> paths) {
    generatedImagePaths = paths;
    notifyListeners();
  }

  void clearGeneratedImages() {
    generatedImagePaths.clear();
    notifyListeners();
  }

  void addChatMessage(String role, String content) {
    chatHistory.add({"role": role, "content": content});
    notifyListeners();
  }

  void removeLastChatMessage() {
    if (chatHistory.isNotEmpty) {
      chatHistory.removeLast();
      notifyListeners();
    }
  }

  void addKbFile(String name) {
    if (!kbFiles.contains(name)) kbFiles.add(name);
    notifyListeners();
  }

  void addMediaFile(String name) {
    if (!mediaFiles.contains(name)) mediaFiles.add(name);
    notifyListeners();
  }

  void clearKbFiles() {
    kbFiles.clear();
    notifyListeners();
  }

  void clearMediaFiles() {
    mediaFiles.clear();
    notifyListeners();
  }

  void clearOutputs() {
    outputs.clear();
    outputFileUrls.clear();
    generatedImagePaths.clear();
    chatHistory.clear();
    notifyListeners();
  }
}