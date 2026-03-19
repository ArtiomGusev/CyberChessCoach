package com.example.myapplication

import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancel
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ChessViewModelTest {

    private lateinit var viewModel: ChessViewModel
    // Explicit scheduler prevents StandardTestDispatcher() from calling
    // getCurrentTestScheduler(), which requires Dispatchers.Main to already be
    // a TestMainDispatcher. Without this, the test fails when another test class
    // runs before it and the process-wide Main dispatcher is in the default state.
    // See the identical pattern and explanation in ChessViewModelEngineFailureTest.
    private val scheduler = TestCoroutineScheduler()
    private val testDispatcher = StandardTestDispatcher(scheduler)

    // 🛡️ Safe mock for testing
    private class FakeEngine : EngineProvider {
        override fun getBestMove(fen: String): AIMove {
            return AIMove(0, 0, 1, 1)
        }
    }

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        viewModel = ChessViewModel(FakeEngine())
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `test AI move is discarded after reset`() = runTest(testDispatcher) {
        var aiMoveApplied = false
        
        // 1. Trigger human move
        viewModel.onHumanMove(
            fr = 6, fc = 4, tr = 4, tc = 4,
            applyHumanMove = { MoveResult.SUCCESS }, // Use extracted enum
            exportFEN = { "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b" },
            applyAIMove = { _, _, _, _ -> aiMoveApplied = true }
        )

        // Give the coroutine a moment to start
        advanceTimeBy(10)

        // 2. Immediately reset the ViewModel
        viewModel.reset()

        // 3. Complete all pending tasks
        advanceUntilIdle()

        // 4. Verify that the AI move was never applied
        assertFalse("AI move should have been discarded after reset", aiMoveApplied)

        // Cancel in-flight Dispatchers.Default coroutines before tearDown calls
        // resetMain(), following the same pattern as ChessViewModelEngineFailureTest.
        // Without this, a Default-thread continuation that dispatches to Main after
        // resetMain() races and throws "Dispatchers.Main is used concurrently with
        // setting it", contaminating subsequent test classes.
        viewModel.viewModelScope.cancel()
        advanceUntilIdle()
    }
}
