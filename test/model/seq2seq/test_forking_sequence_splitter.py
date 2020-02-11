# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

# Third-party imports
import numpy as np

# First-party imports
import pytest

from gluonts import transform
from gluonts.dataset.common import ListDataset
from gluonts.dataset.field_names import FieldName
from gluonts.model.seq2seq._transform import ForkingSequenceSplitter

# if we import TestSplitSampler as Test... pytest thinks it's a test
from gluonts.transform import TestSplitSampler as TSplitSampler
from gluonts.time_feature import time_features_from_frequency_str


def make_dataset(N, train_length):
    # generates 2 ** N - 1 timeseries with constant increasing values
    n = 2 ** N - 1

    targets = np.arange(n * train_length).reshape((n, train_length))

    return ListDataset(
        [{"start": "2012-01-01", "target": targets[i, :]} for i in range(n)],
        freq="D",
    )


def test_forking_sequence_splitter() -> None:
    ds = make_dataset(1, 20)

    trans = transform.Chain(
        trans=[
            transform.AddAgeFeature(
                target_field=FieldName.TARGET,
                output_field="age",
                pred_length=10,
            ),
            ForkingSequenceSplitter(
                train_sampler=TSplitSampler(),
                enc_len=5,
                dec_len=3,
                encoder_series_fields=["age"],
            ),
        ]
    )

    out = trans(iter(ds), is_train=True)
    transformed_data = next(iter(out))

    future_target = np.array(
        [
            [13.0, 14.0, 15.0],
            [14.0, 15.0, 16.0],
            [15.0, 16.0, 17.0],
            [16.0, 17.0, 18.0],
            [17.0, 18.0, 19.0],
        ]
    )

    assert (
        np.linalg.norm(future_target - transformed_data["future_target"])
        < 1e-5
    ), "the forking sequence target should be computed correctly."

    trans_oob = transform.Chain(
        trans=[
            transform.AddAgeFeature(
                target_field=FieldName.TARGET,
                output_field="age",
                pred_length=10,
            ),
            ForkingSequenceSplitter(
                train_sampler=TSplitSampler(),
                enc_len=20,
                dec_len=20,
                encoder_series_fields=["age"],
            ),
        ]
    )

    transformed_data_oob = next(iter(trans_oob(iter(ds), is_train=True)))

    assert (
        np.sum(transformed_data_oob["future_target"]) - np.sum(np.arange(20))
        < 1e-5
    ), "the forking sequence target should be computed correctly."


@pytest.mark.parametrize("is_train", [True, False])
def test_forking_sequence_with_features(is_train) -> None:
    def make_dataset(N, train_length):
        # generates 2 ** N - 1 timeseries with constant increasing values
        n = 2 ** N - 1

        targets = np.arange(n * train_length).reshape((n, train_length))

        return ListDataset(
            [
                {"start": "2012-01-01", "target": targets[i, :]}
                for i in range(n)
            ],
            freq="D",
        )

    ds = make_dataset(1, 20)

    trans = transform.Chain(
        trans=[
            transform.AddAgeFeature(
                target_field=FieldName.TARGET,
                output_field=FieldName.FEAT_AGE,
                pred_length=10,
            ),
            transform.AddTimeFeatures(
                start_field=FieldName.START,
                target_field=FieldName.TARGET,
                output_field=FieldName.FEAT_TIME,
                time_features=time_features_from_frequency_str("D"),
                pred_length=10,
            ),
            ForkingSequenceSplitter(
                train_sampler=TSplitSampler(),
                enc_len=5,
                dec_len=3,
                target_in=FieldName.TARGET,
                encoder_series_fields=[
                    FieldName.FEAT_AGE,
                    FieldName.FEAT_TIME,
                ],
                decoder_series_fields=[FieldName.FEAT_TIME],
            ),
        ]
    )

    out = trans(iter(ds), is_train=is_train)
    transformed_data = next(iter(out))

    assert transformed_data["past_target"].shape == (5, 1)
    assert transformed_data["past_feat_dynamic_age"].shape == (5, 1)
    assert transformed_data["past_time_feat"].shape == (5, 3)
    assert transformed_data["future_time_feat"].shape == (5, 3, 3)

    if is_train:
        assert transformed_data["future_target"].shape == (5, 3)
