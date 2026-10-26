package com.industrial.defect.repository.keyboard;
import com.industrial.defect.entity.keyboard.KeyboardInspection; import org.springframework.data.jpa.repository.JpaRepository; import org.springframework.data.jpa.repository.JpaSpecificationExecutor; import java.util.UUID;
public interface KeyboardInspectionRepository extends JpaRepository<KeyboardInspection, UUID>, JpaSpecificationExecutor<KeyboardInspection> {}
