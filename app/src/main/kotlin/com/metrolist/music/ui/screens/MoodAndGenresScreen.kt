/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.ui.screens

import android.content.res.Configuration.ORIENTATION_LANDSCAPE
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.metrolist.music.LocalPlayerAwareWindowInsets
import com.metrolist.music.R
import com.metrolist.music.ui.component.IconButton
import com.metrolist.music.ui.component.LocalRightPaneScrollBridge
import com.metrolist.music.ui.component.NavigationTitle
import com.metrolist.music.ui.component.shimmer.ListItemPlaceHolder
import com.metrolist.music.ui.component.shimmer.ShimmerHost
import com.metrolist.music.ui.utils.backToMain
import com.metrolist.music.viewmodels.MoodAndGenresViewModel
import timber.log.Timber

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MoodAndGenresScreen(
    navController: NavController,
    viewModel: MoodAndGenresViewModel = hiltViewModel(),
) {
    val localConfiguration = LocalConfiguration.current
    val itemsPerRow = if (localConfiguration.orientation == ORIENTATION_LANDSCAPE) 3 else 2
    val moodAndGenresList by viewModel.moodAndGenres.collectAsStateWithLifecycle()
    val lazyListState = rememberLazyListState()
    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }

    DisposableEffect(rightPaneScrollBridge, lazyListState) {
        if (rightPaneScrollBridge != null) {
            rightPaneScrollBridge.register(
                owner = rightPaneScrollOwner,
                handler = { delta -> lazyListState.dispatchRawDelta(delta) },
                tapHandler = { positionInRoot ->
                    val target = rightPaneTapTargets.values.lastOrNull { (bounds, _) -> bounds.contains(positionInRoot) }
                    if (target != null) {
                        Timber.tag("Dudu7MoodGenreTap").i(
                            "Bridged MoodAndGenres tap x=%.1f y=%.1f",
                            positionInRoot.x,
                            positionInRoot.y,
                        )
                        target.second.invoke()
                        true
                    } else {
                        false
                    }
                },
            )
        }
        onDispose {
            rightPaneScrollBridge?.unregister(rightPaneScrollOwner)
            rightPaneTapTargets.clear()
        }
    }

    LazyColumn(
        state = lazyListState,
        contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
        userScrollEnabled = rightPaneScrollBridge == null,
    ) {
        if (moodAndGenresList == null) {
            item(key = "mood_and_genres_shimmer") {
                ShimmerHost(modifier = Modifier.animateItem()) {
                    repeat(8) { ListItemPlaceHolder() }
                }
            }
        }

        moodAndGenresList?.forEachIndexed { sectionIndex, moodAndGenres ->
            item(key = "mood_and_genres_section_$sectionIndex") {
                Column(
                    modifier = Modifier
                        .animateItem()
                        .padding(horizontal = 6.dp),
                ) {
                    NavigationTitle(title = moodAndGenres.title)
                    moodAndGenres.items.chunked(itemsPerRow).forEach { row ->
                        Row {
                            row.forEach { moodGenreItem ->
                                val targetKey =
                                    "mood_genre_${moodGenreItem.endpoint.browseId}_${moodGenreItem.endpoint.params}_${moodGenreItem.title}"
                                val onItemClick: () -> Unit = {
                                    val route =
                                        "youtube_browse/${moodGenreItem.endpoint.browseId}?params=${moodGenreItem.endpoint.params}"
                                    Timber.tag("Dudu7MoodGenreNavigate").i(
                                        "navigate title=%s browseId=%s route=%s",
                                        moodGenreItem.title,
                                        moodGenreItem.endpoint.browseId,
                                        route,
                                    )
                                    navController.navigate(route)
                                }

                                DisposableEffect(targetKey, rightPaneScrollBridge) {
                                    onDispose { rightPaneTapTargets.remove(targetKey) }
                                }

                                val interactionModifier =
                                    if (rightPaneScrollBridge != null) {
                                        Modifier
                                            .focusable()
                                            .onKeyEvent { event ->
                                                val activate =
                                                    event.type == KeyEventType.KeyUp &&
                                                        event.key in setOf(
                                                            Key.DirectionCenter,
                                                            Key.Enter,
                                                            Key.NumPadEnter,
                                                            Key.Spacebar,
                                                        )
                                                if (activate) {
                                                    onItemClick()
                                                    true
                                                } else {
                                                    false
                                                }
                                            }
                                            .semantics {
                                                onClick {
                                                    onItemClick()
                                                    true
                                                }
                                            }
                                    } else {
                                        Modifier.clickable(onClick = onItemClick)
                                    }

                                MoodAndGenresButton(
                                    title = moodGenreItem.title,
                                    onClick = onItemClick,
                                    applyClickModifier = false,
                                    modifier = Modifier
                                        .weight(1f)
                                        .padding(6.dp)
                                        .onGloballyPositioned { coordinates ->
                                            if (rightPaneScrollBridge != null) {
                                                val bounds = coordinates.boundsInRoot()
                                                val previous = rightPaneTapTargets[targetKey]?.first
                                                rightPaneTapTargets[targetKey] = bounds to onItemClick
                                                if (previous != bounds) {
                                                    Timber.tag("Dudu7MoodGenreTarget").i(
                                                        "title=%s browseId=%s bounds=[%.1f,%.1f,%.1f,%.1f]",
                                                        moodGenreItem.title,
                                                        moodGenreItem.endpoint.browseId,
                                                        bounds.left,
                                                        bounds.top,
                                                        bounds.right,
                                                        bounds.bottom,
                                                    )
                                                }
                                            } else {
                                                rightPaneTapTargets.remove(targetKey)
                                            }
                                        }
                                        .then(interactionModifier),
                                )
                            }

                            repeat(itemsPerRow - row.size) {
                                Spacer(Modifier.weight(1f))
                            }
                        }
                    }
                }
            }
        }
    }

    TopAppBar(
        title = { Text(stringResource(R.string.mood_and_genres)) },
        navigationIcon = {
            IconButton(
                onClick = navController::navigateUp,
                onLongClick = navController::backToMain,
            ) {
                Icon(painterResource(R.drawable.arrow_back), contentDescription = null)
            }
        },
    )
}

@Composable
fun MoodAndGenresButton(
    title: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    applyClickModifier: Boolean = true,
) {
    Box(
        contentAlignment = Alignment.CenterStart,
        modifier = modifier
            .height(MoodAndGenresButtonHeight)
            .clip(RoundedCornerShape(6.dp))
            .background(MaterialTheme.colorScheme.surfaceContainer)
            .then(if (applyClickModifier) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(horizontal = 12.dp),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.labelLarge,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

val MoodAndGenresButtonHeight = 48.dp
