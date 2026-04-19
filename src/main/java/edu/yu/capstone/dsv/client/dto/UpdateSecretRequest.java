package edu.yu.capstone.dsv.client.dto;

public record UpdateSecretRequest(
        String secretCurrentName,
        String secretUpdatedValue,
        String authKey
) {
}


