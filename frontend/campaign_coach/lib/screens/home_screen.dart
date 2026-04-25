import 'package:flutter/material.dart';
import '../widgets/input_section.dart';
import '../widgets/output_section.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.rocket_launch, color: Color(0xFF00F5FF), size: 32),
            SizedBox(width: 16),
            Text(
              "The Campaign Coach",
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF0A0A0F), Color(0xFF1A1A2E)],
          ),
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1800),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Expanded(
                    flex: 4,
                    child: InputSection(),
                  ),
                  SizedBox(width: 24),
                  Expanded(
                    flex: 7,
                    child: OutputSection(),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}