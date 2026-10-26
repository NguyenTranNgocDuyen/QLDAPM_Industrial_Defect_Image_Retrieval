package com.industrial.defect.repository.keyboard;
import com.industrial.defect.entity.keyboard.KeyboardDefect; import org.springframework.data.jpa.repository.JpaRepository; import java.util.UUID;
public interface KeyboardDefectRepository extends JpaRepository<KeyboardDefect, UUID> {}
