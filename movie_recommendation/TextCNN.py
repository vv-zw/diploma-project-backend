# TextCNN.py
import numpy as np
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Embedding, Conv1D, GlobalMaxPooling1D, Dense, Dropout, Concatenate


class TextCNN:
    """TextCNN文本特征提取模型"""

    def __init__(self, max_words=2000, max_len=100, embedding_dim=128):
        self.max_words = max_words
        self.max_len = max_len
        self.embedding_dim = embedding_dim
        self.tokenizer = Tokenizer(num_words=max_words)
        self.model = self._build_model()

    def _build_model(self):
        """构建TextCNN模型"""
        inputs = Input(shape=(self.max_len,))

        # 嵌入层
        embedding = Embedding(
            input_dim=self.max_words,
            output_dim=self.embedding_dim,
            input_length=self.max_len
        )(inputs)

        # 卷积层
        conv1 = Conv1D(128, 3, activation='relu')(embedding)
        pool1 = GlobalMaxPooling1D()(conv1)

        conv2 = Conv1D(128, 4, activation='relu')(embedding)
        pool2 = GlobalMaxPooling1D()(conv2)

        conv3 = Conv1D(128, 5, activation='relu')(embedding)
        pool3 = GlobalMaxPooling1D()(conv3)

        # 拼接
        concat = Concatenate()([pool1, pool2, pool3])
        dropout = Dropout(0.5)(concat)

        # 特征输出层
        outputs = Dense(256, activation='relu')(dropout)

        model = Model(inputs=inputs, outputs=outputs)
        return model

    def fit(self, texts):
        """训练tokenizer并预处理文本"""
        self.tokenizer.fit_on_texts(texts)
        sequences = self.tokenizer.texts_to_sequences(texts)
        self.padded_sequences = pad_sequences(sequences, maxlen=self.max_len)

        # 预热模型（运行一次预测）
        if len(self.padded_sequences) > 0:
            self.model.predict(self.padded_sequences[:min(100, len(self.padded_sequences))], verbose=0)

    def extract_features(self, text):
        """提取文本特征向量"""
        sequence = self.tokenizer.texts_to_sequences([text])
        padded = pad_sequences(sequence, maxlen=self.max_len)
        features = self.model.predict(padded, verbose=0)
        return features[0]