package edu.yu.capstone.dsv.client.dto;

public record UpdateSecretRequest(
        String secretName,
        String secretUpdatedValue,
        String authKey
) {
}
