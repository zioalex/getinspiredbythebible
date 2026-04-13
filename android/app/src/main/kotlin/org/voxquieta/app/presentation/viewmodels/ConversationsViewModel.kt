package org.voxquieta.app.presentation.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import org.voxquieta.app.domain.models.Conversation
import org.voxquieta.app.domain.repositories.ChatRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ConversationsViewModel @Inject constructor(
    private val repository: ChatRepository,
) : ViewModel() {

    private val _isLoading = MutableStateFlow(true)
    /** True until the first emission from [repository.observeConversations] arrives. */
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    val conversations: StateFlow<List<Conversation>> = repository
        .observeConversations()
        .onEach { _isLoading.value = false }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5_000),
            initialValue = emptyList(),
        )

    fun deleteConversation(conversation: Conversation) {
        viewModelScope.launch {
            repository.deleteConversation(conversation.id)
        }
    }

    fun clearAll() {
        viewModelScope.launch {
            repository.clearAllConversations()
        }
    }
}
