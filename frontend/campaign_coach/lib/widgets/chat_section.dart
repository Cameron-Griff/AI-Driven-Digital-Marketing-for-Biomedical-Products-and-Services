import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/campaign_provider.dart';

class ChatSection extends StatefulWidget {
  const ChatSection({super.key});

  @override
  State<ChatSection> createState() => _ChatSectionState();
}

class _ChatSectionState extends State<ChatSection> {
  final TextEditingController _controller = TextEditingController();
  bool _isSending = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _sendMessage(BuildContext context) async {
    if (_isSending) return;

    final provider = context.read<CampaignProvider>();
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    final question = _controller.text.trim();

    if (question.isEmpty) return;

    final outputs = provider.outputs;
    if (outputs.isEmpty) {
      scaffoldMessenger.showSnackBar(
        const SnackBar(content: Text('Generate campaign outputs first.')),
      );
      return;
    }

    final previousHistory =
        List<Map<String, String>>.from(provider.chatHistory);

    provider.addChatMessage('user', question);
    _controller.clear();

    setState(() {
      _isSending = true;
    });

    try {
      final dio = Dio();
      final response = await dio.post(
        'http://localhost:8000/chat_outputs',
        data: {
          'question': question,
          'history': previousHistory,
          'plan': outputs['plan'] ?? '',
          'playbooks': outputs['playbooks'] ?? '',
          'calendar': outputs['calendar'] ?? '',
          'examples': outputs['examples'] ?? '',
        },
        options: Options(
          sendTimeout: const Duration(seconds: 60),
          receiveTimeout: const Duration(seconds: 180),
          contentType: Headers.jsonContentType,
        ),
      );

      if (!mounted) return;

      if (response.statusCode == 200 && response.data['status'] == 'success') {
        final reply = response.data['data']?['reply']?.toString().trim() ?? '';
        if (reply.isEmpty) {
          throw Exception('The chatbot returned an empty response.');
        }
        provider.addChatMessage('assistant', reply);
      } else {
        final message =
            response.data['message']?.toString() ?? 'Unknown error';
        throw Exception(message);
      }
    } on DioException catch (e) {
      if (!mounted) return;

      if (provider.chatHistory.isNotEmpty &&
          provider.chatHistory.last['role'] == 'user' &&
          provider.chatHistory.last['content'] == question) {
        provider.removeLastChatMessage();
      }

      String message = 'Connection error. Is backend running?';

      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.sendTimeout ||
          e.type == DioExceptionType.receiveTimeout) {
        message = 'Chatbot request timed out.';
      } else if (e.response != null &&
          e.response?.data is Map &&
          e.response?.data['message'] != null) {
        message = e.response?.data['message'].toString() ?? message;
      } else if (e.message != null) {
        message = e.message!;
      }

      scaffoldMessenger.showSnackBar(
        SnackBar(
          content: Text('❌ $message'),
          backgroundColor: Colors.red,
        ),
      );
    } catch (e) {
      if (!mounted) return;

      if (provider.chatHistory.isNotEmpty &&
          provider.chatHistory.last['role'] == 'user' &&
          provider.chatHistory.last['content'] == question) {
        provider.removeLastChatMessage();
      }

      scaffoldMessenger.showSnackBar(
        SnackBar(
          content: Text('❌ $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSending = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<CampaignProvider>(context);
    final hasOutputs = provider.outputs.isNotEmpty;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Campaign Chatbot',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            Text(
              hasOutputs
                  ? 'Ask anything about your generated strategy, content calendar, or playbooks.'
                  : 'Generate campaign outputs first, then discuss the results with the chatbot.',
              style: const TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 16),
            if (provider.chatHistory.isNotEmpty) ...[
              ...provider.chatHistory.map((msg) {
                final isUser = msg['role'] == 'user';
                return Align(
                  alignment: isUser
                      ? Alignment.centerRight
                      : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 12,
                    ),
                    constraints: const BoxConstraints(maxWidth: 720),
                    decoration: BoxDecoration(
                      color: isUser
                          ? const Color(0xFF7B5EFF).withValues(alpha: 0.18)
                          : Colors.white.withValues(alpha: 0.04),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: isUser
                            ? const Color(0xFF7B5EFF).withValues(alpha: 0.45)
                            : Colors.white.withValues(alpha: 0.08),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isUser ? 'You' : 'Campaign Coach',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: isUser
                                ? const Color(0xFFB7A5FF)
                                : const Color(0xFF00F5FF),
                          ),
                        ),
                        const SizedBox(height: 6),
                        SelectableText(msg['content'] ?? ''),
                      ],
                    ),
                  ),
                );
              }),
              const SizedBox(height: 8),
            ],
            TextField(
              enabled: hasOutputs && !_isSending,
              controller: _controller,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _sendMessage(context),
              decoration: InputDecoration(
                hintText: hasOutputs
                    ? 'Type your question...'
                    : 'Generate campaign outputs first...',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                suffixIcon: _isSending
                    ? const Padding(
                        padding: EdgeInsets.all(12),
                        child: SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      )
                    : IconButton(
                        icon: const Icon(Icons.send),
                        onPressed:
                            hasOutputs ? () => _sendMessage(context) : null,
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}