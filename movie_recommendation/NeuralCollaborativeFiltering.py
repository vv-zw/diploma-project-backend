# NeuralCollaborativeFiltering.py
import numpy as np
import json
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Embedding, Flatten, Dot, Dense, Concatenate, Dropout
from tensorflow.keras.optimizers import Adam


class NeuralCollaborativeFiltering:
    def __init__(self, user_id="user_default", embedding_size=32):
        self.user_id = user_id
        self.embedding_size = embedding_size
        self.model = None
        self.item2idx = {}
        self.id2item = {}

    def _build_model(self, num_items):
        user_input = Input(shape=(1,), name='user_input')
        item_input = Input(shape=(1,), name='item_input')

        # GMF部分
        user_embedding_gmf = Embedding(1, self.embedding_size)(user_input)
        item_embedding_gmf = Embedding(num_items, self.embedding_size)(item_input)
        gmf_vector = Dot(axes=-1)([Flatten()(user_embedding_gmf), Flatten()(item_embedding_gmf)])

        # MLP部分
        user_embedding_mlp = Embedding(1, self.embedding_size * 2)(user_input)
        item_embedding_mlp = Embedding(num_items, self.embedding_size * 2)(item_input)
        mlp_vector = Concatenate()([Flatten()(user_embedding_mlp), Flatten()(item_embedding_mlp)])
        mlp_vector = Dense(64, activation='relu')(mlp_vector)
        mlp_vector = Dropout(0.2)(mlp_vector)
        mlp_vector = Dense(32, activation='relu')(mlp_vector)

        concat_vector = Concatenate()([gmf_vector, mlp_vector])
        output = Dense(1, activation='sigmoid')(concat_vector)

        self.model = Model(inputs=[user_input, item_input], outputs=output)
        self.model.compile(optimizer=Adam(learning_rate=0.001),
                           loss='binary_crossentropy',
                           metrics=['accuracy'])

    def prepare_data_from_json(self, user_preferences, user_behavior, movie_data):
        all_items = [item['id'] for item in movie_data]
        self.item2idx = {item_id: idx for idx, item_id in enumerate(all_items)}
        self.id2item = {idx: item_id for item_id, idx in self.item2idx.items()}

        positive_items = []
        for pref in user_preferences:
            item_id = pref.get('id')
            if item_id in self.item2idx:
                positive_items.append(self.item2idx[item_id])

        for behavior in user_behavior:
            if behavior.get('type') == 'like' and behavior.get('item_id') in self.item2idx:
                positive_items.append(self.item2idx[behavior.get('item_id')])

        interacted_items = set(positive_items)
        all_item_indices = set(range(len(all_items)))
        negative_candidates = list(all_item_indices - interacted_items)
        negative_items = np.random.choice(
            negative_candidates,
            size=min(len(positive_items) * 2, len(negative_candidates)),
            replace=False
        ).tolist()

        user_input_data = np.zeros(len(positive_items) + len(negative_items))
        item_input_data = np.array(positive_items + negative_items)
        labels = np.array([1] * len(positive_items) + [0] * len(negative_items))

        shuffle_indices = np.random.permutation(len(user_input_data))
        return (
            user_input_data[shuffle_indices],
            item_input_data[shuffle_indices],
            labels[shuffle_indices]
        )

    def train(self, user_preferences, user_behavior, movie_data):
        user_input, item_input, labels = self.prepare_data_from_json(user_preferences, user_behavior, movie_data)
        self._build_model(len(self.item2idx))
        self.model.fit([user_input, item_input], labels, epochs=5, batch_size=16, verbose=0)

    def predict_scores(self, movie_data):
        item_indices = np.array(list(self.item2idx.values()))
        user_indices = np.zeros(len(item_indices))

        predictions = self.model.predict([user_indices, item_indices], verbose=0)
        scores = {}
        for idx, score in zip(item_indices, predictions.flatten()):
            item_id = self.id2item[idx]
            scores[item_id] = float(score)
        return scores