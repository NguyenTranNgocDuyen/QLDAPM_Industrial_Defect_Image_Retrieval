package com.industrial.defect.dto;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class ImageSizeDto {

    private int width;
    private int height;
    private String url;
    private String coordinateSpace;

    public ImageSizeDto() {
    }

    public ImageSizeDto(int width, int height) {
        this.width = width;
        this.height = height;
    }

    public ImageSizeDto(int width, int height, String url, String coordinateSpace) {
        this.width = width;
        this.height = height;
        this.url = url;
        this.coordinateSpace = coordinateSpace;
    }

    public int getWidth() {
        return width;
    }

    public void setWidth(int width) {
        this.width = width;
    }

    public int getHeight() {
        return height;
    }

    public void setHeight(int height) {
        this.height = height;
    }

    public String getUrl() {
        return url;
    }

    public void setUrl(String url) {
        this.url = url;
    }

    public String getCoordinateSpace() {
        return coordinateSpace;
    }

    public void setCoordinateSpace(String coordinateSpace) {
        this.coordinateSpace = coordinateSpace;
    }
}
