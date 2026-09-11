-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 8.4.1                                       //
-- // Date : 2020-03-18                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V8.4.0

UPDATE `${prefix}resourceteamaffectation` RTA 
SET startDate=(select R1.startDate from ${prefix}resource R1 WHERE R1.id=RTA.idResource) 
WHERE (select R2.startDate from ${prefix}resource R2 WHERE R2.id=RTA.idResource) is not null 
AND ( (select R3.startDate from ${prefix}resource R3 WHERE R3.id=RTA.idResource) < RTA.startDate OR RTA.startDate is NULL);

ALTER TABLE `${prefix}columnselector` CHANGE `sortOrder` `sortOrder` INT(10) COMMENT '10';
